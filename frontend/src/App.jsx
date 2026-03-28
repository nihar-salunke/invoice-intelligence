import { useState } from "react";
import ImageUpload from "./components/ImageUpload";
import ResultCard from "./components/ResultCard";
import ImagePreview from "./components/ImagePreview";
import History from "./components/History";
import "./App.css";

export default function App() {
  const [result, setResult] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const handleResult = (data) => {
    setResult(data);
    setRefreshKey((k) => k + 1);
  };

  return (
    <div className="app">
      <header className="header">
        <div className="header-content">
          <h1>Invoice Intelligence</h1>
        </div>
      </header>

      <main className="main">
        <div className="left-panel">
          <section className="upload-section">
            <h2>Upload Invoice</h2>
            <ImageUpload onResult={handleResult} onProcessing={setProcessing} />
            {processing && (
              <div className="processing-indicator">
                <div className="spinner" />
                <span>Analyzing invoice...</span>
              </div>
            )}
          </section>

          {result && !result.error && (
            <section className="result-section">
              <h2>Extracted Fields</h2>
              <div className="result-with-preview">
                {result.imageUrl && (
                  <ImagePreview imageUrl={result.imageUrl} fields={result.fields} />
                )}
                <ResultCard result={result} />
              </div>
            </section>
          )}

          {result?.error && (
            <section className="result-section">
              <ResultCard result={result} />
            </section>
          )}
        </div>

        <aside className="right-panel">
          <History refreshKey={refreshKey} onSelect={setResult} />
        </aside>
      </main>
    </div>
  );
}
