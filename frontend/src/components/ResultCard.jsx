export default function ResultCard({ result }) {
  if (!result) return null;

  if (result.error) {
    return (
      <div className="result-card error-card">
        <h3>Extraction Failed</h3>
        <p>{result.error}</p>
      </div>
    );
  }

  const { fields, confidence, processing_time_sec, doc_id } = result;
  const confPct = Math.round((confidence || 0) * 100);

  const formatCost = (val) => {
    if (!val) return "N/A";
    return `₹${val.toLocaleString("en-IN")}`;
  };

  return (
    <div className="result-card">
      <div className="result-header">
        <h3>{doc_id}</h3>
        <span className="processing-time">{processing_time_sec}s</span>
      </div>

      <div className="fields-grid">
        <div className="field-row">
          <label>Dealer Name</label>
          <span className="field-value">{fields.dealer_name || "N/A"}</span>
        </div>
        <div className="field-row">
          <label>Model</label>
          <span className="field-value">{fields.model_name || "N/A"}</span>
        </div>
        <div className="field-row">
          <label>Horse Power</label>
          <span className="field-value">{fields.horse_power ? `${fields.horse_power} HP` : "N/A"}</span>
        </div>
        <div className="field-row">
          <label>Asset Cost</label>
          <span className="field-value cost">{formatCost(fields.asset_cost)}</span>
        </div>
      </div>

      <div className="badges-row">
        <span className={`badge ${fields.signature?.present ? "badge-green" : "badge-red"}`}>
          {fields.signature?.present ? "✓ Signature" : "✗ No Signature"}
        </span>
        <span className={`badge ${fields.stamp?.present ? "badge-green" : "badge-red"}`}>
          {fields.stamp?.present ? "✓ Stamp" : "✗ No Stamp"}
        </span>
      </div>

      <div className="confidence-section">
        <div className="confidence-label">
          <span>Confidence</span>
          <span>{confPct}%</span>
        </div>
        <div className="confidence-bar">
          <div
            className="confidence-fill"
            style={{ width: `${confPct}%` }}
          />
        </div>
      </div>
    </div>
  );
}
