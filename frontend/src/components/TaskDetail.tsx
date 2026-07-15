import React, { useState } from 'react';
import type { Task, TaskKind } from '../types';
import { useTasks } from '../hooks/useTasks';

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

/** Convert datetime string to a local datetime-local input value. */
function toInputValue(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const KIND_CONFIG: Record<TaskKind, { icon: string; label: string; color: string }> = {
  event:     { icon: '📅', label: '时间段事件', color: 'bg-emerald-100 text-emerald-700' },
  deadline:  { icon: '🔴', label: '截止日',     color: 'bg-red-100 text-red-700' },
  milestone: { icon: '⭐', label: '纪念日',     color: 'bg-purple-100 text-purple-700' },
};

const CATEGORY_LABELS: Record<string, string> = {
  social: '社交', meal: '用餐', work: '工作', health: '健康',
  medical: '医疗', education: '学习', entertainment: '娱乐',
  travel: '旅行', transport: '交通', chore: '杂务',
  personal: '个人', finance: '财务', holiday: '节日',
};

interface Props {
  task: Task;
  onClose: () => void;
  onDelete?: (id: string) => void;
}

export default function TaskDetail({ task, onClose, onDelete }: Props) {
  const { updateTask } = useTasks();
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(task.title);
  const [startDt, setStartDt] = useState(toInputValue(task.datetime));
  const [endDt, setEndDt] = useState(task.end_datetime ? toInputValue(task.end_datetime) : '');
  const [kind, setKind] = useState(task.kind || 'event');
  const [saving, setSaving] = useState(false);

  const kindCfg = KIND_CONFIG[kind as TaskKind] || KIND_CONFIG.event;
  const catLabel = task.category ? (CATEGORY_LABELS[task.category] || task.category) : null;

  const handleSave = async () => {
    if (!title.trim()) return;
    setSaving(true);
    try {
      await updateTask(task.id, {
        title: title.trim(),
        datetime: new Date(startDt).toISOString(),
        end_datetime: endDt ? new Date(endDt).toISOString() : (null as any),
        kind: kind as TaskKind,
      });
      setEditing(false);
      onClose();
    } catch { /* error handled by context */ }
    setSaving(false);
  };

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
          <div className="flex-1 mr-3">
            <div className="flex items-center gap-2 mb-1">
              {editing ? (
                <select
                  value={kind}
                  onChange={(e) => setKind(e.target.value)}
                  className="px-2 py-0.5 rounded text-[11px] font-medium bg-gray-100 border border-gray-200"
                >
                  <option value="event">📅 事件</option>
                  <option value="deadline">🔴 截止</option>
                  <option value="milestone">⭐ 纪念</option>
                </select>
              ) : (
                <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${kindCfg.color}`}>
                  {kindCfg.icon} {kindCfg.label}
                </span>
              )}
              {catLabel && (
                <span className="px-2 py-0.5 rounded text-[10px] bg-gray-100 text-gray-500">{catLabel}</span>
              )}
            </div>
            {editing ? (
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full text-lg font-bold border-b border-gray-200 pb-1 outline-none focus:border-indigo-400"
              />
            ) : (
              <h2 className="text-xl font-bold text-gray-900">{task.title}</h2>
            )}
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg">✕</button>
        </div>

        <div className="space-y-3 text-sm">
          <div>
            <span className="text-gray-400">状态</span>
            <p className="text-gray-700">{statusLabels[task.status] || task.status}</p>
          </div>

          {/* ── Time (always editable) ── */}
          <div>
            <span className="text-gray-400">{kind === 'event' ? '起止时间' : '时间点'}</span>
            {editing ? (
              <div className="space-y-1.5 mt-1">
                <input
                  type="datetime-local"
                  value={startDt}
                  onChange={(e) => setStartDt(e.target.value)}
                  className="w-full px-2 py-1 border border-gray-200 rounded text-xs"
                />
                {kind === 'event' && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] text-gray-400">至</span>
                    <input
                      type="datetime-local"
                      value={endDt}
                      onChange={(e) => setEndDt(e.target.value)}
                      className="flex-1 px-2 py-1 border border-gray-200 rounded text-xs"
                    />
                    {endDt && (
                      <button
                        onClick={() => setEndDt('')}
                        className="text-[10px] text-red-400 hover:text-red-600"
                      >清除</button>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <>
                <p className="text-gray-700">{formatDateTime(task.datetime)}</p>
                {task.end_datetime && kind === 'event' && (
                  <p className="text-gray-500">至 {formatDateTime(task.end_datetime)}</p>
                )}
              </>
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

        <div className="flex gap-2 mt-4">
          {editing ? (
            <>
              <button
                onClick={handleSave}
                disabled={saving || !title.trim()}
                className="flex-1 py-2 bg-indigo-600 text-white rounded-lg font-medium text-sm hover:bg-indigo-700 disabled:opacity-40 transition-colors"
              >
                {saving ? '保存中...' : '保存'}
              </button>
              <button
                onClick={() => {
                  setTitle(task.title);
                  setStartDt(toInputValue(task.datetime));
                  setEndDt(task.end_datetime ? toInputValue(task.end_datetime) : '');
                  setKind(task.kind || 'event');
                  setEditing(false);
                }}
                className="flex-1 py-2 border border-gray-200 text-gray-600 rounded-lg text-sm hover:bg-gray-50"
              >
                取消
              </button>
            </>
          ) : (
            <>
              {onDelete && (
                <button
                  onClick={() => onDelete(task.id)}
                  className="flex-1 py-2 border border-red-200 text-red-600 rounded-lg hover:bg-red-50 transition-colors text-sm"
                >
                  删除
                </button>
              )}
              <button
                onClick={() => setEditing(true)}
                className="flex-1 py-2 border border-gray-200 text-gray-600 rounded-lg hover:bg-gray-50 transition-colors text-sm"
              >
                ✏️ 编辑
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
