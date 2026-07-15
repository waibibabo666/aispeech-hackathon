import React, { useState, useCallback, useRef } from 'react';
import { useDropzone } from 'react-dropzone';
import { useTasks } from '../hooks/useTasks';
import { transcribeVoice } from '../api/client';

type ResultMsg = { type: 'ok' | 'warn' | 'error'; text: string };

export default function InputPanel() {
  const [text, setText] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [result, setResult] = useState<ResultMsg | null>(null);
  const { uploadFiles, sendIntent, loading, error } = useTasks();

  // ── Voice state (declared early so handleSubmit can stop it) ──
  const mediaSupported = !!navigator.mediaDevices?.getUserMedia;
  const [listening, setListening] = useState(false);
  const ctxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Float32Array[]>([]);
  const totalRef = useRef(0);
  const lastSentRef = useRef(0);
  const pendingRef = useRef(false);
  const timerRef = useRef<number>(0);
  const prevTextRef = useRef('');      // text before current recording started
  const voiceVersionRef = useRef(0);  // monotonic — stale callbacks ignored
  const typedByUser = useRef(false);  // true if user manually typed/edited text

  const onDrop = useCallback((accepted: File[]) => {
    setFiles((prev) => [...prev, ...accepted]);
    setResult(null);
    setExpanded(true);
  }, []);

  const removeFile = (name: string) => {
    setFiles((prev) => prev.filter((f) => f.name !== name));
  };

  const handleSubmit = async () => {
    if (!text.trim() && files.length === 0) return;
    if (loading) return;
    setResult(null);

    // Stop voice recording if active.
    // Bump version — all in-flight async callbacks will see mismatch and bail.
    if (listening) {
      voiceVersionRef.current += 1;
      clearInterval(timerRef.current);
      ctxRef.current?.close();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      ctxRef.current = null;
      streamRef.current = null;
      setListening(false);
    }

    // Snap text NOW before clearing — race-free
    const submitText = text.trim();
    setText('');

    // ── File upload path — always extract ──
    // Don't send voice transcript alongside file content (would cause duplicates)
    if (files.length > 0) {
      try {
        const res = await uploadFiles(files, typedByUser.current ? submitText : '');
        if (res.result.auto_added > 0 || res.result.pending_review > 0) {
          setResult({ type: 'ok', text: `✅ 新增 ${res.result.auto_added} 个任务` });
        } else {
          setResult({ type: 'warn', text: '未识别到日程，请检查文件内容' });
        }
      } catch { setResult(null); }
      setFiles([]);
      return;
    }

    // ── Text-only path — unified intent dispatch ──
    try {
      const res = await sendIntent(submitText);

      if (res.action === 'extract') {
        if (res.auto_added > 0) {
          setResult({ type: 'ok', text: `✅ 新增 ${res.auto_added} 个任务` + (res.pending_review ? `，${res.pending_review} 个待确认` : '') });
        } else {
          setResult({ type: 'warn', text: '未识别到日程信息' });
        }
      } else if (res.action === 'delete') {
        if (res.deleted_count > 0) {
          setResult({ type: 'ok', text: `🗑️ ${res.summary || `已删除 ${res.deleted_count} 个任务`}` });
        } else {
          setResult({ type: 'warn', text: res.summary || '未找到匹配的任务' });
        }
      } else {
        // chat
        setResult({ type: 'ok', text: res.reply || res.summary || '好的' });
      }
    } catch { setResult(null); }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleSubmit();
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop, disabled: loading, maxSize: 25 * 1024 * 1024,
  });

  const hasContent = text.trim().length > 0 || files.length > 0;

  // ── Voice input: stream PCM chunks → SenseVoice → real-time text ──

  function encodeWav(samples: Float32Array, sampleRate: number): Blob {
    const numChannels = 1;
    const bitsPerSample = 16;
    const byteRate = sampleRate * numChannels * bitsPerSample / 8;
    const blockAlign = numChannels * bitsPerSample / 8;
    const dataLen = samples.length * 2;
    const buf = new ArrayBuffer(44 + dataLen);
    const view = new DataView(buf);
    writeStr(view, 0, 'RIFF');
    view.setUint32(4, 36 + dataLen, true);
    writeStr(view, 8, 'WAVE');
    writeStr(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, byteRate, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, bitsPerSample, true);
    writeStr(view, 36, 'data');
    view.setUint32(40, dataLen, true);
    for (let i = 0; i < samples.length; i++) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(44 + i * 2, s < 0 ? s * 32768 : s * 32767, true);
    }
    return new Blob([buf], { type: 'audio/wav' });
  }

  function writeStr(view: DataView, offset: number, str: string) {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
  }

  /** Send accumulated audio to SenseVoice, return new text delta. */
  async function sendChunk(allChunks: Float32Array[], total: number, sampleRate: number): Promise<string> {
    const combined = new Float32Array(total);
    let off = 0;
    for (const c of allChunks) { combined.set(c, off); off += c.length; }
    const wav = encodeWav(combined, sampleRate);
    const res = await transcribeVoice(wav);
    return res.text;
  }

  const toggleVoice = useCallback(async () => {
    if (!mediaSupported) return;

    if (listening) {
      // Stop recording
      clearInterval(timerRef.current);
      if (ctxRef.current && (ctxRef.current as any).__cleanup) {
        (ctxRef.current as any).__cleanup();
      }
      ctxRef.current = null;
      streamRef.current = null;
      setListening(false);
      // Remove trailing ellipsis
      setText((prev) => prev.replace(/⋯$/, ''));
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const ctx = new AudioContext({ sampleRate: 16000 });
      ctxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const processor = ctx.createScriptProcessor(4096, 1, 1);

      chunksRef.current = [];
      totalRef.current = 0;
      lastSentRef.current = 0;
      pendingRef.current = false;
      // Start new recording session — bump version so old callbacks are ignored
      voiceVersionRef.current += 1;
      const recordingVer = voiceVersionRef.current;

      // Capture current text so we can append new transcription to it
      prevTextRef.current = text.trimEnd();

      processor.onaudioprocess = (e) => {
        const data = new Float32Array(e.inputBuffer.getChannelData(0));
        chunksRef.current.push(data);
        totalRef.current += data.length;
      };

      source.connect(processor);
      processor.connect(ctx.destination);

      // Every 2 seconds, send accumulated audio for real-time transcription
      const sampleRate = ctx.sampleRate;
      timerRef.current = window.setInterval(async () => {
        if (pendingRef.current || totalRef.current === lastSentRef.current) return;
        pendingRef.current = true;
        try {
          const text = await sendChunk(chunksRef.current, totalRef.current, sampleRate);
          if (voiceVersionRef.current !== recordingVer) return;
          lastSentRef.current = totalRef.current;
          // Show real-time text: previous base + current transcription + ellipsis
          typedByUser.current = false;
          setText(prevTextRef.current ? `${prevTextRef.current} ${text}⋯` : `${text}⋯`);
        } catch { /* ignore interim errors */ }
        pendingRef.current = false;
      }, 1000);

      // Cleanup on stop (called via the stop path)
      (ctx as any).__cleanup = async () => {
        clearInterval(timerRef.current);
        processor.disconnect();
        source.disconnect();
        stream.getTracks().forEach((t) => t.stop());
        await ctx.close();

        if (totalRef.current === 0 || voiceVersionRef.current !== recordingVer) return;

        // Final transcription — replace interim text with final result
        try {
          const result = await sendChunk(chunksRef.current, totalRef.current, sampleRate);
          if (voiceVersionRef.current !== recordingVer) return;
          const base = prevTextRef.current;
          typedByUser.current = false;
          setText(base ? `${base} ${result}` : result);
          setExpanded(true);
        } catch (e: any) {
          setResult({ type: 'error', text: e.message || '转录失败' });
        }
        chunksRef.current = [];
        totalRef.current = 0;
      };

      setListening(true);
      setExpanded(true);
      setResult(null);
    } catch (e: any) {
      setResult({ type: 'error', text: '无法访问麦克风' });
    }
  }, [mediaSupported, listening]);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-3">
      <div className="flex gap-3">
        <div className="flex-1 relative">
          <textarea
            value={text}
            onChange={(e) => { setText(e.target.value); typedByUser.current = true; if (e.target.value) setExpanded(true); setResult(null); }}
            onFocus={() => setExpanded(true)}
            onKeyDown={handleKeyDown}
            placeholder="粘贴文本、拖入文件提取日程…  也可以输入「删除所有晚餐」来删除任务  (Ctrl+Enter 提交)"
            className="w-full p-2.5 pr-9 border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm leading-relaxed placeholder:text-gray-400"
            rows={expanded ? 4 : 2}
            disabled={loading}
          />
          {mediaSupported && (
            <button
              type="button"
              onClick={toggleVoice}
              disabled={loading}
              title={listening ? '停止录音' : '语音输入'}
              className={`absolute right-2 bottom-2 w-7 h-7 flex items-center justify-center rounded-full transition-all ${
                listening
                  ? 'bg-red-500 text-white animate-pulse shadow-lg shadow-red-300'
                  : 'bg-gray-100 text-gray-400 hover:bg-indigo-100 hover:text-indigo-600'
              }`}
            >
              {listening ? '⏹' : '🎤'}
            </button>
          )}
        </div>

        <div className="flex flex-col gap-2 min-w-[140px]">
          <div
            {...getRootProps()}
            className={`flex-1 flex items-center justify-center border-2 border-dashed rounded-lg px-2 py-1 text-center cursor-pointer transition-colors ${
              isDragActive ? 'border-indigo-400 bg-indigo-50' : 'border-gray-300 hover:border-gray-400 bg-gray-50/50'
            }`}
          >
            <input {...getInputProps()} />
            <span className="text-xs text-gray-500">{isDragActive ? '📂 松开上传' : '📎 选择文件'}</span>
          </div>

          <button
            onClick={handleSubmit}
            disabled={!hasContent || loading}
            className="w-full py-2 bg-indigo-600 text-white rounded-lg font-medium text-sm hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? '处理中...' : '发送'}
          </button>
        </div>
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {files.map((f) => (
            <span key={f.name} className="inline-flex items-center gap-1 bg-gray-100 px-2 py-1 rounded text-xs text-gray-600">
              📄 {f.name} ({(f.size / 1024).toFixed(0)}KB)
              <button onClick={() => removeFile(f.name)} className="text-red-400 hover:text-red-600 ml-0.5" disabled={loading}>✕</button>
            </span>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded-lg text-red-700 text-xs">{error}</div>
      )}

      {/* Result */}
      {result && !loading && (
        <div className={`mt-2 p-2 rounded-lg text-xs ${
          result.type === 'ok' ? 'bg-emerald-50 border border-emerald-200 text-emerald-800' :
          result.type === 'warn' ? 'bg-amber-50 border border-amber-200 text-amber-700' :
          'bg-red-50 border border-red-200 text-red-700'
        }`}>
          {result.text}
        </div>
      )}
    </div>
  );
}
