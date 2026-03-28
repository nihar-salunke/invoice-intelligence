export default function AgentTrail({ trail }) {
  if (!trail || !trail.length) return null;

  const statusIcon = (s) => {
    if (s === "pass") return "check";
    if (s === "warn") return "warn";
    return "fail";
  };

  const agentLabels = {
    intake: "Intake Agent",
    extraction: "Extraction Agent",
    research: "Research Agent",
    validation: "Validation Agent",
    scoring: "Scoring Agent",
  };

  return (
    <div className="agent-trail">
      <h3>Agent Pipeline</h3>
      <div className="trail-timeline">
        {trail.map((step, i) => (
          <div key={i} className={`trail-step trail-${step.status}`}>
            <div className="trail-dot-col">
              <div className={`trail-dot dot-${step.status}`} />
              {i < trail.length - 1 && <div className="trail-line" />}
            </div>
            <div className="trail-content">
              <div className="trail-header">
                <span className="trail-agent">{agentLabels[step.agent] || step.agent}</span>
                <span className="trail-time">{step.time_sec}s</span>
              </div>
              <p className="trail-decision">{step.decision}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
