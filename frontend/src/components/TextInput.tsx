import React, { useState } from 'react';
import { useTasks } from '../hooks/useTasks';

export default function TextInput() {
  const [text, setText] = useState('');
  const { extractText, loading } = useTasks();

  const handleSubmit = async () => {
    if (!text.trim() || loading) return;
    await extractText(text);
    setText('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      handleSubmit();
    }
  };

  return (
    <div>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="在这里粘贴聊天记录、会议笔记、或直接描述你的日程安排...&#10;&#10;例如：&#10;周五下午三点在3楼会议室和产品团队开Q3规划会&#10;下周找个时间和Alice吃午饭"
        className="w-full h-40 p-4 border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm leading-relaxed"
        disabled={loading}
      />
      <div className="flex items-center justify-between mt-3">
        <span className="text-xs text-gray-400">
          {text.length} 字 | Ctrl+Enter 发送
        </span>
        <button
          onClick={handleSubmit}
          disabled={!text.trim() || loading}
          className="px-6 py-2.5 bg-indigo-600 text-white rounded-lg font-medium text-sm hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? '提取中...' : '提取任务'}
        </button>
      </div>
    </div>
  );
}
