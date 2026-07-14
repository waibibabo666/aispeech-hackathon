import React, { useState } from 'react';
import FullCalendar from '@fullcalendar/react';
import timeGridPlugin from '@fullcalendar/timegrid';
import dayGridPlugin from '@fullcalendar/daygrid';
import listPlugin from '@fullcalendar/list';
import interactionPlugin from '@fullcalendar/interaction';
import type { EventClickArg } from '@fullcalendar/core';
import { useTasks } from '../hooks/useTasks';
import type { Task } from '../types';
import TaskDetail from './TaskDetail';

function taskToEvent(task: Task) {
  const color =
    task.status === 'auto_confirmed'
      ? '#10b981'
      : task.status === 'confirmed'
        ? '#f59e0b'
        : task.status === 'pending'
          ? '#9ca3af'
          : '#ef4444';

  return {
    id: task.id,
    title: task.title,
    start: task.datetime,
    end: task.end_datetime || undefined,
    backgroundColor: color,
    borderColor: color,
    extendedProps: { task },
  };
}

export default function TaskTimeline() {
  const { tasks, deleteTask } = useTasks();
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [view, setView] = useState<'timeGridWeek' | 'dayGridMonth' | 'listWeek'>('timeGridWeek');

  const events = tasks.map(taskToEvent);

  const handleEventClick = (info: EventClickArg) => {
    setSelectedTask(info.event.extendedProps.task as Task);
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">📅 任务时间线</h2>
        <div className="flex gap-2">
          {([
            ['timeGridWeek', '周'],
            ['dayGridMonth', '月'],
            ['listWeek', '列表'],
          ] as const).map(([v, label]) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                view === v
                  ? 'bg-indigo-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <FullCalendar
        key={view}
        plugins={[timeGridPlugin, dayGridPlugin, listPlugin, interactionPlugin]}
        initialView={view}
        events={events}
        eventClick={handleEventClick}
        headerToolbar={false}
        height="auto"
        locale="zh-cn"
        firstDay={1}
        allDaySlot={false}
        nowIndicator={true}
        slotMinTime="07:00:00"
        slotMaxTime="22:00:00"
      />

      {tasks.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          <div className="text-4xl mb-2">📭</div>
          <p>暂无任务，在上方输入文本或上传文件开始</p>
        </div>
      )}

      {selectedTask && (
        <TaskDetail
          task={selectedTask}
          onClose={() => setSelectedTask(null)}
          onDelete={(id) => {
            deleteTask(id);
            setSelectedTask(null);
          }}
        />
      )}
    </div>
  );
}
