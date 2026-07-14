import React, { useState } from 'react';
import { useTasks } from '../hooks/useTasks';
import TextInput from './TextInput';
import FileUpload from './FileUpload';

export default function InputPanel() {
  const [tab, setTab] = useState<'text' | 'file'>('text');
  const { loading, error } = useTasks();

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
      <div className="flex gap-4 mb-4">
        <button
          onClick={() => setTab('text')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            tab === 'text'
              ? 'bg-indigo-600 text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          ✏️ 文字输入
        </button>
        <button
          onClick={() => setTab('file')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            tab === 'file'
              ? 'bg-indigo-600 text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          📁 文件上传
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      {loading && (
        <div className="mb-4 flex items-center gap-2 text-indigo-600 text-sm">
          <div className="animate-spin w-4 h-4 border-2 border-indigo-600 border-t-transparent rounded-full" />
          AI正在分析提取中...
        </div>
      )}

      {tab === 'text' ? <TextInput /> : <FileUpload />}
    </div>
  );
}
