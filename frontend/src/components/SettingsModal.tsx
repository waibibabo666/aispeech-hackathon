import React, { useState, useEffect } from 'react';

interface ApiConfig {
  llm_api_key: string;
  llm_base_url: string;
  llm_model_name: string;
}

interface Props {
  onClose: () => void;
}

export default function SettingsModal({ onClose }: Props) {
  const [config, setConfig] = useState<ApiConfig>({
    llm_api_key: '',
    llm_base_url: '',
    llm_model_name: '',
  });
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  // Track whether the user has a saved API key (masked by backend as ***)
  const [hasSavedKey, setHasSavedKey] = useState(false);

  const loadConfig = () => {
    setLoading(true);
    setLoadError(false);
    fetch('/api/config')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        const isMasked = data.llm_api_key === '***';
        setHasSavedKey(isMasked);
        setConfig({
          llm_api_key: isMasked ? '' : (data.llm_api_key || ''),
          llm_base_url: data.llm_base_url || '',
          llm_model_name: data.llm_model_name || '',
        });
        setLoading(false);
      })
      .catch(() => {
        setLoadError(true);
        setLoading(false);
      });
  };

  useEffect(() => {
    loadConfig();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const payload = {
        llm_api_key: config.llm_api_key || (hasSavedKey ? '' : ''),
        llm_base_url: config.llm_base_url,
        llm_model_name: config.llm_model_name,
      };
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || '保存失败');
      }
      const data = await res.json();
      setHasSavedKey(data.config?.llm_api_key === '***');
      setMessage({ type: 'success', text: '✓ 配置已保存，立即生效' });
      setTimeout(() => onClose(), 1000);
    } catch (e: any) {
      setMessage({ type: 'error', text: e.message || '保存失败' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/30 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">⚙️ 设置</h2>
            <p className="text-xs text-gray-400 mt-0.5">本地模型状态 · LLM API 配置</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-lg leading-none"
          >
            ✕
          </button>
        </div>

        <div className="p-5 space-y-6">
          {/* ==================== LOCAL MODELS ==================== */}
          <div>
            <h3 className="text-sm font-semibold text-gray-800 mb-3">📦 本地模型（已启用，无需配置）</h3>
            <div className="space-y-2">
              <div className="flex items-center gap-3 p-3 bg-emerald-50 border border-emerald-200 rounded-lg">
                <span className="text-xl">🖼️</span>
                <div>
                  <span className="text-sm font-medium text-gray-900">图片文字识别</span>
                  <span className="ml-2 text-xs bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded-full">RapidOCR</span>
                  <p className="text-xs text-gray-500 mt-0.5">~30MB，中文优化，离线可用</p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 bg-emerald-50 border border-emerald-200 rounded-lg">
                <span className="text-xl">🎙️</span>
                <div>
                  <span className="text-sm font-medium text-gray-900">语音转文字</span>
                  <span className="ml-2 text-xs bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded-full">SenseVoice-Small</span>
                  <p className="text-xs text-gray-500 mt-0.5">~227MB，中文准确率 96%+，离线可用</p>
                </div>
              </div>
            </div>
          </div>

          {/* Divider */}
          <div className="border-t border-gray-200" />

          {/* ==================== LLM API ==================== */}
          <div>
            <h3 className="text-sm font-semibold text-gray-800 mb-1">☁️ LLM API 配置</h3>
            <p className="text-xs text-gray-400 mb-4 leading-relaxed">
              本地模型负责将图片和音频中的文字提取出来。你需要配置一个大语言模型 API
              来理解这些文字并输出结构化日程。支持所有兼容 OpenAI Chat API 的服务。
            </p>

            {loading ? (
              <div className="flex items-center gap-2 text-sm text-gray-400 py-4">
                <div className="animate-spin w-4 h-4 border-2 border-gray-300 border-t-indigo-500 rounded-full" />
                加载已有配置...
              </div>
            ) : loadError ? (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg mb-4">
                <p className="text-sm text-amber-700">
                  ⚠️ 无法加载已有配置，请检查后端服务是否启动。
                </p>
                <button
                  onClick={loadConfig}
                  className="mt-2 text-xs text-indigo-600 hover:text-indigo-800 underline"
                >
                  点击重试
                </button>
              </div>
            ) : null}

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  API Key <span className="text-red-400">*</span>
                  {hasSavedKey && (
                    <span className="ml-2 text-xs bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded-full">
                      ✓ 已配置
                    </span>
                  )}
                </label>
                <input
                  type="password"
                  value={config.llm_api_key}
                  onChange={(e) => {
                    setConfig({ ...config, llm_api_key: e.target.value });
                    if (e.target.value) setHasSavedKey(false);
                  }}
                  placeholder={hasSavedKey ? '已保存（留空则不修改）' : 'sk-...'}
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
                {hasSavedKey && (
                  <p className="text-xs text-gray-400 mt-1">
                    已有 API Key，如需更换请输入新 Key，留空则不修改
                  </p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">API 地址</label>
                <input
                  type="text"
                  value={config.llm_base_url}
                  onChange={(e) => setConfig({ ...config, llm_base_url: e.target.value })}
                  placeholder="https://api.openai.com/v1"
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  模型名称 <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={config.llm_model_name}
                  onChange={(e) => setConfig({ ...config, llm_model_name: e.target.value })}
                  placeholder="gpt-4o / deepseek-chat / qwen-plus ..."
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>
            </div>

            <div className="mt-4 p-3 bg-indigo-50 border border-indigo-200 rounded-lg">
              <p className="text-xs text-indigo-700 leading-relaxed">
                <strong>兼容服务：</strong>OpenAI（gpt-4o）、DeepSeek（deepseek-chat）、
                阿里百炼（qwen-plus）、智谱（glm-4）、Moonshot 等。
                填入 API Key、地址和模型名即可使用。
              </p>
            </div>
          </div>

          {/* Message */}
          {message && (
            <div
              className={`p-3 rounded-lg text-sm ${
                message.type === 'success'
                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  : 'bg-red-50 text-red-700 border border-red-200'
              }`}
            >
              {message.text}
            </div>
          )}

          {/* Persistence info */}
          <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg">
            <p className="text-xs text-gray-500 leading-relaxed">
              💾 配置保存在 <code className="bg-gray-200 px-1 rounded">data/runtime_config.json</code>，
              重启后自动加载。
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="p-5 border-t border-gray-200 flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 border border-gray-300 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={saving || loading}
            className="flex-1 py-2.5 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {saving ? '保存中...' : loading ? '加载中...' : '保存配置'}
          </button>
        </div>
      </div>
    </div>
  );
}
