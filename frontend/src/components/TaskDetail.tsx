import React from 'react';
import type { Task } from '../types';

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

interface Props {
  task: Task;
  onClose: () => void;
  onDelete?: (id: string) => void;
}

export default function TaskDetail({ task, onClose, onDelete }: Props) {
  const statusLabels: Record<string, string> = {
    auto_confirmed: '✅ 自动确认',
    confirmed: '👍 已确认',
    pending: '⏳ 待确认',
    rejected: '❌ 已拒绝',
  };

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <h2 className="text-xl font-bold text-gray-900">{task.title}</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-lg"
          >
            ✕
          </button>
        </div>

        <div className="space-y-3 text-sm">
          <div>
            <span className="text-gray-400">状态</span>
            <p className="text-gray-700">{statusLabels[task.status] || task.status}</p>
          </div>
          <div>
            <span className="text-gray-400">时间</span>
            <p className="text-gray-700">{formatDateTime(task.datetime)}</p>
            {task.end_datetime && (
              <p className="text-gray-500">至 {formatDateTime(task.end_datetime)}</p>
            )}
          </div>
          {task.location && (
            <div>
              <span className="text-gray-400">地点</span>
              <p className="text-gray-700">{task.location}</p>
            </div>
          )}
          {task.attendees.length > 0 && (
            <div>
              <span className="text-gray-400">参与者</span>
              <p className="text-gray-700">{task.attendees.join(', ')}</p>
            </div>
          )}
          {task.notes && (
            <div>
              <span className="text-gray-400">备注</span>
              <p className="text-gray-700">{task.notes}</p>
            </div>
          )}
          <div>
            <span className="text-gray-400">置信度</span>
            <p className="text-gray-700">{Math.round(task.confidence * 100)}%</p>
          </div>
          <div>
            <span className="text-gray-400">来源</span>
            <p className="text-gray-700">{task.source}</p>
          </div>
        </div>

        {onDelete && (
          <button
            onClick={() => onDelete(task.id)}
            className="mt-4 w-full py-2 border border-red-200 text-red-600 rounded-lg hover:bg-red-50 transition-colors text-sm"
          >
            删除任务
          </button>
        )}
      </div>
    </div>
  );
}
