import React, { useState } from 'react';
import { useTasks } from '../hooks/useTasks';

export default function PendingBadge() {
  const { pendingTasks } = useTasks();
  const [show, setShow] = useState(false);

  if (pendingTasks.length === 0) return null;

  return (
    <>
      <button
        onClick={() => setShow(true)}
        className="fixed bottom-6 right-6 z-40 bg-red-500 text-white w-14 h-14 rounded-full shadow-lg flex items-center justify-center hover:bg-red-600 transition-colors animate-bounce"
      >
        <span className="text-lg font-bold">{pendingTasks.length}</span>
      </button>

      {show && <ConfidenceModal onClose={() => setShow(false)} />}
    </>
  );
}

function ConfidenceModal({ onClose }: { onClose: () => void }) {
  const { pendingTasks, confirmTask, rejectTask } = useTasks();
  const [processing, setProcessing] = useState<Set<string>>(new Set());

  const handleConfirm = async (id: string) => {
    setProcessing((p) => new Set(p).add(id));
    await confirmTask(id);
    setProcessing((p) => {
      const next = new Set(p);
      next.delete(id);
      return next;
    });
  };

  const handleReject = async (id: string) => {
    setProcessing((p) => new Set(p).add(id));
    await rejectTask(id);
    setProcessing((p) => {
      const next = new Set(p);
      next.delete(id);
      return next;
    });
  };

  const handleConfirmAll = async () => {
    for (const t of pendingTasks) {
      await handleConfirm(t.id);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4 max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold">
            ⏳ 待确认任务 ({pendingTasks.length})
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            ✕
          </button>
        </div>

        <div className="overflow-y-auto p-4 space-y-3 flex-1">
          {pendingTasks.map((task) => (
            <div key={task.id} className="border border-gray-200 rounded-lg p-3">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-medium text-gray-900">{task.title}</h3>
                  <p className="text-sm text-gray-500 mt-1">
                    {new Date(task.datetime).toLocaleString('zh-CN')}
                  </p>
                  {task.location && (
                    <p className="text-xs text-gray-400">📍 {task.location}</p>
                  )}
                </div>
                <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">
                  {Math.round(task.confidence * 100)}%
                </span>
              </div>

              <div className="flex gap-2 mt-3">
                <button
                  onClick={() => handleConfirm(task.id)}
                  disabled={processing.has(task.id)}
                  className="flex-1 py-1.5 bg-emerald-500 text-white rounded-lg text-sm font-medium hover:bg-emerald-600 disabled:opacity-50 transition-colors"
                >
                  ✓ 确认
                </button>
                <button
                  onClick={() => handleReject(task.id)}
                  disabled={processing.has(task.id)}
                  className="flex-1 py-1.5 bg-gray-200 text-gray-600 rounded-lg text-sm font-medium hover:bg-gray-300 disabled:opacity-50 transition-colors"
                >
                  ✕ 忽略
                </button>
              </div>
            </div>
          ))}

          {pendingTasks.length === 0 && (
            <div className="text-center py-8 text-gray-400">所有任务已处理 ✓</div>
          )}
        </div>

        {pendingTasks.length > 1 && (
          <div className="p-4 border-t border-gray-200">
            <button
              onClick={handleConfirmAll}
              className="w-full py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors"
            >
              全部确认
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
