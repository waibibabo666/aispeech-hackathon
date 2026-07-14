import React, { createContext, useContext, useReducer, useCallback } from 'react';
import type { Task, UploadResponse } from '../types';
import * as api from '../api/client';

interface TaskState {
  tasks: Task[];
  pendingTasks: Task[];
  loading: boolean;
  error: string | null;
}

type Action =
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'SET_TASKS'; payload: Task[] }
  | { type: 'SET_PENDING'; payload: Task[] }
  | { type: 'ADD_TASKS'; payload: Task[] }
  | { type: 'UPDATE_TASK'; payload: Task }
  | { type: 'REMOVE_TASK'; payload: string };

function reducer(state: TaskState, action: Action): TaskState {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, loading: action.payload };
    case 'SET_ERROR':
      return { ...state, error: action.payload };
    case 'SET_TASKS':
      return { ...state, tasks: action.payload };
    case 'SET_PENDING':
      return { ...state, pendingTasks: action.payload };
    case 'ADD_TASKS': {
      const newTasks = [...state.tasks];
      const newPending = [...state.pendingTasks];
      for (const t of action.payload) {
        if (t.status === 'pending') {
          newPending.push(t);
        } else {
          newTasks.push(t);
        }
      }
      return { ...state, tasks: newTasks, pendingTasks: newPending };
    }
    case 'UPDATE_TASK': {
      const updated = action.payload;
      if (updated.status === 'pending') return state;
      return {
        ...state,
        tasks: updated.status === 'rejected'
          ? state.tasks.filter(t => t.id !== updated.id)
          : [...state.tasks.filter(t => t.id !== updated.id), updated],
        pendingTasks: state.pendingTasks.filter(t => t.id !== updated.id),
      };
    }
    case 'REMOVE_TASK':
      return {
        ...state,
        tasks: state.tasks.filter(t => t.id !== action.payload),
      };
    default:
      return state;
  }
}

const initialState: TaskState = {
  tasks: [],
  pendingTasks: [],
  loading: false,
  error: null,
};

interface TaskContextValue extends TaskState {
  extractText: (text: string) => Promise<UploadResponse>;
  uploadFiles: (files: File[]) => Promise<UploadResponse>;
  refreshTasks: () => Promise<void>;
  refreshPending: () => Promise<void>;
  confirmTask: (id: string) => Promise<void>;
  rejectTask: (id: string) => Promise<void>;
  deleteTask: (id: string) => Promise<void>;
  loadDemo: () => Promise<void>;
}

const TaskContext = createContext<TaskContextValue | null>(null);

export function TaskProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  const wrap = useCallback(async <T,>(fn: () => Promise<T>): Promise<T> => {
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });
    try {
      const result = await fn();
      return result;
    } catch (e: any) {
      dispatch({ type: 'SET_ERROR', payload: e.message || 'Unknown error' });
      throw e;
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, []);

  const extractText = useCallback(async (text: string) => {
    const res = await wrap(() => api.extractFromText(text));
    dispatch({ type: 'ADD_TASKS', payload: res.result.tasks });
    return res;
  }, [wrap]);

  const uploadFilesFn = useCallback(async (files: File[]) => {
    const res = await wrap(() => api.uploadFiles(files));
    dispatch({ type: 'ADD_TASKS', payload: res.result.tasks });
    return res;
  }, [wrap]);

  const refreshTasks = useCallback(async () => {
    const tasks = await wrap(() => api.getTasks());
    dispatch({ type: 'SET_TASKS', payload: tasks });
  }, [wrap]);

  const refreshPending = useCallback(async () => {
    const pending = await wrap(() => api.getPendingTasks());
    dispatch({ type: 'SET_PENDING', payload: pending });
  }, [wrap]);

  const confirmTaskFn = useCallback(async (id: string) => {
    const task = await wrap(() => api.confirmTask(id));
    dispatch({ type: 'UPDATE_TASK', payload: task });
  }, [wrap]);

  const rejectTaskFn = useCallback(async (id: string) => {
    await wrap(() => api.rejectTask(id));
    // Find the task to update it locally
    dispatch({
      type: 'UPDATE_TASK',
      payload: { id, status: 'rejected' } as Task,
    } as any);
  }, [wrap]);

  const deleteTaskFn = useCallback(async (id: string) => {
    await wrap(() => api.deleteTask(id));
    dispatch({ type: 'REMOVE_TASK', payload: id });
  }, [wrap]);

  const loadDemo = useCallback(async () => {
    const tasks = await wrap(() => api.loadDemoTasks());
    dispatch({ type: 'SET_TASKS', payload: tasks });
    dispatch({ type: 'SET_PENDING', payload: [] });
  }, [wrap]);

  return (
    <TaskContext.Provider
      value={{
        ...state,
        extractText,
        uploadFiles: uploadFilesFn,
        refreshTasks,
        refreshPending,
        confirmTask: confirmTaskFn,
        rejectTask: rejectTaskFn,
        deleteTask: deleteTaskFn,
        loadDemo,
      }}
    >
      {children}
    </TaskContext.Provider>
  );
}

export function useTasks() {
  const ctx = useContext(TaskContext);
  if (!ctx) throw new Error('useTasks must be used within TaskProvider');
  return ctx;
}
