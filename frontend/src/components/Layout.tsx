import React, { useState, useEffect } from 'react';
import PendingBadge from './PendingBadge';
import SettingsModal from './SettingsModal';

export default function Layout({ children }: { children: React.ReactNode }) {
  const [showSettings, setShowSettings] = useState(false);
  const [llmReady, setLlmReady] = useState<boolean | null>(null);

  useEffect(() => {
    fetch('/api/config')
      .then((r) => r.json())
      .then((data) => {
        setLlmReady(!!(data.llm_api_key && data.llm_model_name));
      })
      .catch(() => setLlmReady(false));
  }, []);

  return (
    <div className="h-full flex flex-col bg-gray-50 overflow-hidden">
      {/* Header */}
      <header className="flex-shrink-0 bg-white border-b border-gray-200">
        <div className="pl-4 pr-2 h-11 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-lg">📅</span>
            <h1 className="text-sm font-bold text-gray-900">日知</h1>
            {llmReady !== null && (
              <span
                className={`hidden sm:inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded-full ${
                  llmReady
                    ? 'bg-emerald-100 text-emerald-700'
                    : 'bg-amber-100 text-amber-700'
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${llmReady ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                {llmReady ? 'API 已连接' : 'API 未配置'}
              </span>
            )}
          </div>
          <div className="flex items-center gap-0.5">
            <button
              onClick={() => setShowSettings(true)}
              className="px-2 py-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded text-sm transition-colors"
              title="设置"
            >
              ⚙️
            </button>
          </div>
        </div>

        {llmReady === false && (
          <div className="bg-amber-50 border-t border-amber-200 px-4 py-1.5 text-center">
            <p className="text-[11px] text-amber-700">
              ⚠️ LLM API 尚未配置，无法提取日程。点击右上角 ⚙️ 配置 API。
            </p>
          </div>
        )}
      </header>

      {/* Main area — fills all remaining space */}
      <main className="flex-1 min-h-0 px-4 py-3">
        {children}
      </main>

      <PendingBadge />

      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
    </div>
  );
}
