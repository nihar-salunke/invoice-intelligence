export default function ImagePreview({ imageUrl, fields }) {
  const boxes = [];

  const sig = fields?.signature;
  if (sig?.present && sig.bbox?.length === 4) {
    boxes.push({ bbox: sig.bbox, label: "Signature", color: "#2979ff" });
  }

  const stamp = fields?.stamp;
  if (stamp?.present && stamp.bbox?.length === 4) {
    boxes.push({ bbox: stamp.bbox, label: "Stamp", color: "#e53935" });
  }

  return (
    <div className="image-preview-container">
      <img src={imageUrl} alt="Invoice" className="preview-image" />
      {boxes.map((box, i) => {
        const [x1, y1, x2, y2] = box.bbox;
        return (
          <div
            key={i}
            className="bbox-overlay"
            style={{
              left: `${x1}%`,
              top: `${y1}%`,
              width: `${x2 - x1}%`,
              height: `${y2 - y1}%`,
              borderColor: box.color,
            }}
          >
            <span className="bbox-label" style={{ backgroundColor: box.color }}>
              {box.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}
