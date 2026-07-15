import type { Task, UploadResponse } from '../types';

const BASE = '/api';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function extractFromText(text: string, source = 'manual-input'): Promise<UploadResponse> {
  return request<UploadResponse>('/extract', {
    method: 'POST',
    body: JSON.stringify({ text, source }),
  });
}

export async function uploadFiles(files: File[], text?: string): Promise<UploadResponse> {
  const formData = new FormData();
  files.forEach((f) => formData.append('files', f));
  if (text?.trim()) {
    formData.append('text', text.trim());
  }
  const res = await fetch(`${BASE}/upload`, { method: 'POST', body: formData });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Upload failed: ${res.status}`);
  }
  return res.json();
}

/** Combined submit: text + files in one API call, single LLM extraction. */
export async function submitAll(text: string, files: File[]): Promise<UploadResponse> {
  if (text.trim() || files.length > 0) {
    return uploadFiles(files, text);
  }
  throw new Error('No text or files to submit');
}

export async function getTasks(): Promise<Task[]> {
  return request<Task[]>('/tasks');
}

export async function getPendingTasks(): Promise<Task[]> {
  return request<Task[]>('/tasks/pending');
}

export async function confirmTask(taskId: string): Promise<Task> {
  return request<Task>(`/tasks/${taskId}/confirm`, { method: 'POST' });
}

export async function rejectTask(taskId: string): Promise<void> {
  return request<void>(`/tasks/${taskId}/reject`, { method: 'POST' });
}

export async function updateTask(taskId: string, updates: Partial<Task>): Promise<Task> {
  return request<Task>(`/tasks/${taskId}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });
}

export async function deleteTask(taskId: string): Promise<void> {
  return request<void>(`/tasks/${taskId}`, { method: 'DELETE' });
}

/** Unified intent API — one call for extract, delete, or chat. */
export async function sendIntent(text: string): Promise<{
  action: string;
  tasks?: Task[];
  auto_added: number;
  pending_review: number;
  discarded: number;
  extracted_text?: string;
  deleted_count: number;
  summary?: string;
  deleted_ids?: string[];
  reply?: string;
}> {
  const res = await fetch(`${BASE}/tasks/intent`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Intent failed: ${res.status}`);
  }
  return res.json();
}

/** Record voice and transcribe via local SenseVoice model. */
export async function transcribeVoice(audioBlob: Blob): Promise<{ text: string; source: string }> {
  const formData = new FormData();
  formData.append('audio', audioBlob, 'voice.wav');
  const res = await fetch(`${BASE}/transcribe-voice`, { method: 'POST', body: formData });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Transcription failed: ${res.status}`);
  }
  return res.json();
}
