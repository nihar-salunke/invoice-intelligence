import { useEffect, useState } from "react";

const API_URL = "http://127.0.0.1:8000";

export default function History({ refreshKey, onSelect }) {
  const [items, setItems] = useState([]);

  useEffect(() => {
    fetch(`${API_URL}/api/results`)
      .then((r) => r.json())
      .then(setItems)
      .catch(() => setItems([]));
  }, [refreshKey]);

  if (!items.length) {
    return (
      <div className="history-panel">
        <h3>Processing History</h3>
        <p className="history-empty">No results yet. Upload an invoice to get started.</p>
      </div>
    );
  }

  const formatCost = (val) => {
    if (!val) return "—";
    return `₹${val.toLocaleString("en-IN")}`;
  };

  return (
    <div className="history-panel">
      <h3>Processing History</h3>
      <div className="history-list">
        {items.map((item) => (
          <div
            key={item.doc_id}
            className="history-item"
            onClick={() => onSelect(item)}
          >
            <div className="history-item-top">
              <span className="history-dealer">{item.fields.dealer_name || "Unknown"}</span>
              <span className="history-conf">{item.scoring?.authenticity_score ?? Math.round((item.confidence || 0) * 100)}</span>
            </div>
            <div className="history-item-bottom">
              <span>{item.fields.model_name || "—"}</span>
              <span>{formatCost(item.fields.asset_cost)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
