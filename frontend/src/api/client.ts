import type { Task, UploadResponse } from '../types';

const BASE = '/api';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function extractFromText(text: string, source = 'manual-input'): Promise<UploadResponse> {
  return request<UploadResponse>('/extract', {
    method: 'POST',
    body: JSON.stringify({ text, source }),
  });
}

export async function uploadFiles(files: File[]): Promise<UploadResponse> {
  const formData = new FormData();
  files.forEach((f) => formData.append('files', f));
  const res = await fetch(`${BASE}/upload`, { method: 'POST', body: formData });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Upload failed: ${res.status}`);
  }
  return res.json();
}

export async function getTasks(): Promise<Task[]> {
  return request<Task[]>('/tasks');
}

export async function getPendingTasks(): Promise<Task[]> {
  return request<Task[]>('/tasks/pending');
}

export async function confirmTask(taskId: string): Promise<Task> {
  return request<Task>(`/tasks/${taskId}/confirm`, { method: 'POST' });
}

export async function rejectTask(taskId: string): Promise<void> {
  return request<void>(`/tasks/${taskId}/reject`, { method: 'POST' });
}

export async function deleteTask(taskId: string): Promise<void> {
  return request<void>(`/tasks/${taskId}`, { method: 'DELETE' });
}

export async function loadDemoTasks(): Promise<Task[]> {
  return request<Task[]>('/tasks/demo', { method: 'POST' });
}
