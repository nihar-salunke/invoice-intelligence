const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export default function ImagePreview({ imageUrl, processedUrl }) {
  return (
    <div className="image-preview-dual">
      <div className="preview-col">
        <span className="preview-label">Original</span>
        <div className="image-preview-container">
          <img src={imageUrl} alt="Original" className="preview-image" />
        </div>
      </div>
      {processedUrl && (
        <div className="preview-col">
          <span className="preview-label">Preprocessed</span>
          <div className="image-preview-container">
            <img
              src={`${API_URL}${processedUrl}`}
              alt="Preprocessed"
              className="preview-image"
            />
          </div>
        </div>
      )}
    </div>
  );
}
