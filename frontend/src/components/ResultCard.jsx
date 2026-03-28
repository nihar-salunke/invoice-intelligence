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

  const { fields, enrichment, research, scoring, processing_time_sec, doc_id } = result;
  const score = scoring?.authenticity_score ?? 0;
  const compliance = scoring?.compliance_status ?? "UNKNOWN";
  const breakdown = scoring?.breakdown ?? {};

  const formatCost = (val) => {
    if (!val) return "N/A";
    return `\u20B9${val.toLocaleString("en-IN")}`;
  };

  const complianceClass =
    compliance === "PASS" ? "compliance-pass" :
    compliance === "REVIEW" ? "compliance-review" : "compliance-fail";

  return (
    <div className="result-card">
      {/* Score header */}
      <div className="score-header">
        <div className="score-ring-container">
          <svg className="score-ring" viewBox="0 0 80 80">
            <circle cx="40" cy="40" r="34" fill="none" stroke="#e0e0e0" strokeWidth="6" />
            <circle
              cx="40" cy="40" r="34" fill="none"
              stroke={score >= 70 ? "#43a047" : score >= 40 ? "#ff9800" : "#e53935"}
              strokeWidth="6"
              strokeDasharray={`${score * 2.136} 213.6`}
              strokeLinecap="round"
              transform="rotate(-90 40 40)"
            />
          </svg>
          <span className="score-number">{score}</span>
        </div>
        <div className="score-info">
          <span className={`compliance-badge ${complianceClass}`}>{compliance}</span>
          <span className="processing-time">{processing_time_sec}s</span>
        </div>
      </div>

      {/* Summary */}
      {scoring?.summary && (
        <p className="result-summary">{scoring.summary}</p>
      )}

      {/* Enrichment badges */}
      {enrichment && (
        <div className="enrichment-row">
          {enrichment.language_detected && (
            <span className="enrich-badge">{enrichment.language_detected}</span>
          )}
          {enrichment.state_detected && (
            <span className="enrich-badge">{enrichment.state_detected}</span>
          )}
          {enrichment.document_type && (
            <span className="enrich-badge">{enrichment.document_type}</span>
          )}
        </div>
      )}

      {/* Extracted fields */}
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

      {/* Signature / Stamp badges */}
      <div className="badges-row">
        <span className={`badge ${fields.signature?.present ? "badge-green" : "badge-red"}`}>
          {fields.signature?.present ? "\u2713 Signature" : "\u2717 No Signature"}
        </span>
        <span className={`badge ${fields.stamp?.present ? "badge-green" : "badge-red"}`}>
          {fields.stamp?.present ? "\u2713 Stamp" : "\u2717 No Stamp"}
        </span>
      </div>

      {/* Research results */}
      {research && (research.model_hp_verified !== undefined || research.dealer_found_online !== undefined) && (
        <div className="research-section">
          <h4>Web Verification</h4>
          <div className="research-row">
            <span className={`research-check ${research.model_hp_verified ? "rc-pass" : "rc-fail"}`}>
              {research.model_hp_verified ? "\u2713" : "\u2717"} HP Verified
              {research.expected_hp > 0 && ` (${research.expected_hp} HP)`}
            </span>
            <span className={`research-check ${research.dealer_found_online ? "rc-pass" : "rc-fail"}`}>
              {research.dealer_found_online ? "\u2713" : "\u2717"} Dealer Verified
            </span>
          </div>
          {research.dealer_search_summary && (
            <p className="research-detail">{research.dealer_search_summary}</p>
          )}
        </div>
      )}

      {/* Score breakdown */}
      {breakdown && Object.keys(breakdown).length > 0 && (
        <div className="breakdown-section">
          <h4>Score Breakdown</h4>
          <div className="breakdown-grid">
            {Object.entries(breakdown).map(([key, val]) => (
              <div key={key} className="breakdown-item">
                <span className="bd-label">{key.replace(/_/g, " ")}</span>
                <span className="bd-value">{val}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
