import React from 'react';
import type { Task } from '../types';

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

function confidenceColor(c: number): string {
  if (c >= 0.8) return 'bg-emerald-100 text-emerald-700';
  if (c >= 0.5) return 'bg-amber-100 text-amber-700';
  return 'bg-gray-100 text-gray-500';
}

function confidenceLabel(c: number): string {
  return `${Math.round(c * 100)}%`;
}

interface Props {
  task: Task;
  onDelete?: (id: string) => void;
}

export default function TaskCard({ task, onDelete }: Props) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <h3 className="font-semibold text-gray-900">{task.title}</h3>
        <span
          className={`text-xs px-2 py-0.5 rounded-full font-medium ${confidenceColor(task.confidence)}`}
        >
          {confidenceLabel(task.confidence)}
        </span>
      </div>

      <div className="mt-2 space-y-1 text-sm text-gray-500">
        <div>
          📅 {formatDate(task.datetime)}{' '}
          {formatTime(task.datetime)}
          {task.end_datetime && ` - ${formatTime(task.end_datetime)}`}
        </div>
        {task.location && <div>📍 {task.location}</div>}
        {task.attendees.length > 0 && (
          <div>👥 {task.attendees.join(', ')}</div>
        )}
        {task.notes && <div className="text-gray-400">💬 {task.notes}</div>}
      </div>

      <div className="mt-3 flex items-center justify-between">
        <span className="text-xs text-gray-400">
          {task.source}
          {task.status === 'pending' && (
            <span className="ml-2 text-amber-500 font-medium">待确认</span>
          )}
        </span>
        {onDelete && (
          <button
            onClick={() => onDelete(task.id)}
            className="text-xs text-red-400 hover:text-red-600 transition-colors"
          >
            删除
          </button>
        )}
      </div>
    </div>
  );
}
