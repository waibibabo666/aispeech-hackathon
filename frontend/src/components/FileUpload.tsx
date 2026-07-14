import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { useTasks } from '../hooks/useTasks';

export default function FileUpload() {
  const [files, setFiles] = useState<File[]>([]);
  const { uploadFiles, loading } = useTasks();

  const onDrop = useCallback((accepted: File[]) => {
    setFiles((prev) => [...prev, ...accepted]);
  }, []);

  const removeFile = (name: string) => {
    setFiles((prev) => prev.filter((f) => f.name !== name));
  };

  const handleSubmit = async () => {
    if (files.length === 0 || loading) return;
    await uploadFiles(files);
    setFiles([]);
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    disabled: loading,
    maxSize: 25 * 1024 * 1024, // 25MB
  });

  const totalSize = files.reduce((sum, f) => sum + f.size, 0);

  return (
    <div>
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-indigo-400 bg-indigo-50'
            : 'border-gray-300 hover:border-gray-400 bg-gray-50'
        }`}
      >
        <input {...getInputProps()} />
        <div className="text-3xl mb-2">📎</div>
        <p className="text-sm text-gray-600">
          {isDragActive ? '松开以上传文件' : '拖拽文件到此处，或点击选择'}
        </p>
        <p className="text-xs text-gray-400 mt-1">
          支持 .txt, .docx, .pdf, .jpg, .png, .mp3, .wav (单文件不超过25MB)
        </p>
      </div>

      {files.length > 0 && (
        <div className="mt-3 space-y-2">
          {files.map((f) => (
            <div
              key={f.name}
              className="flex items-center justify-between bg-gray-50 px-3 py-2 rounded-lg text-sm"
            >
              <span className="truncate">
                📄 {f.name}{' '}
                <span className="text-gray-400">
                  ({(f.size / 1024).toFixed(1)} KB)
                </span>
              </span>
              <button
                onClick={() => removeFile(f.name)}
                className="text-red-500 hover:text-red-700 ml-2"
                disabled={loading}
              >
                ✕
              </button>
            </div>
          ))}
          <div className="flex items-center justify-between mt-3">
            <span className="text-xs text-gray-400">
              {files.length} 个文件, 共 {(totalSize / 1024).toFixed(1)} KB
            </span>
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="px-6 py-2.5 bg-indigo-600 text-white rounded-lg font-medium text-sm hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? '上传解析中...' : '上传并提取'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
