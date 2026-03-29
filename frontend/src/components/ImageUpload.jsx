import { useCallback, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export default function ImageUpload({ onResult, onProcessing }) {
  const [preview, setPreview] = useState(null);
  const [dragActive, setDragActive] = useState(false);

  const handleFile = useCallback(
    async (file) => {
      if (!file || !file.type.startsWith("image/")) return;

      setPreview(URL.createObjectURL(file));
      onProcessing(true);

      const formData = new FormData();
      formData.append("file", file);

      try {
        const res = await fetch(`${API_URL}/api/extract`, {
          method: "POST",
          body: formData,
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "API error");
        }
        const data = await res.json();
        onResult({ ...data, imageUrl: URL.createObjectURL(file) });
      } catch (e) {
        onResult({ error: e.message });
      } finally {
        onProcessing(false);
      }
    },
    [onResult, onProcessing]
  );

  const onDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
  };

  const onDragOver = (e) => {
    e.preventDefault();
    setDragActive(true);
  };

  return (
    <div
      className={`upload-zone ${dragActive ? "drag-active" : ""}`}
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={() => setDragActive(false)}
      onClick={() => document.getElementById("file-input").click()}
    >
      <input
        id="file-input"
        type="file"
        accept="image/*"
        hidden
        onChange={(e) => e.target.files.length && handleFile(e.target.files[0])}
      />
      {preview ? (
        <img src={preview} alt="preview" className="upload-preview" />
      ) : (
        <div className="upload-placeholder">
          <svg width="48" height="48" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 16v-8m0 0l-3 3m3-3l3 3M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1" />
          </svg>
          <p>Drop invoice image here or click to upload</p>
          <span>PNG, JPG supported</span>
        </div>
      )}
    </div>
  );
}
