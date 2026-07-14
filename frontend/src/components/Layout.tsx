import React from 'react';
import { useTasks } from '../hooks/useTasks';
import PendingBadge from './PendingBadge';

export default function Layout({ children }: { children: React.ReactNode }) {
  const { loadDemo, loading } = useTasks();

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">📅</span>
            <h1 className="text-lg font-bold text-gray-900">多模态任务管理器</h1>
          </div>
          <button
            onClick={loadDemo}
            disabled={loading}
            className="px-4 py-2 bg-indigo-50 text-indigo-700 rounded-lg text-sm font-medium hover:bg-indigo-100 disabled:opacity-50 transition-colors"
          >
            🎯 加载Demo
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {children}
      </main>

      <PendingBadge />
    </div>
  );
}
