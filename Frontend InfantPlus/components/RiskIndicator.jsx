import { memo } from "react";

function riskColor(score) {
  if (score >= 75) {
    return "bg-critical text-white";
  }
  if (score >= 45) {
    return "bg-warning text-white";
  }
  return "bg-stable text-white";
}

function RiskIndicatorComponent({ score, label = "Risk", compact = false }) {
  return (
    <div className={`inline-flex items-center gap-3 rounded-full ${compact ? "" : "bg-[#f5fafc] px-3 py-2"}`}>
      <span className={`rounded-full px-3 py-1 text-sm font-semibold ${riskColor(score)}`}>{score}</span>
      {!compact && <span className="text-sm font-medium text-slate">{label}</span>}
    </div>
  );
}

const RiskIndicator = memo(RiskIndicatorComponent);

export default RiskIndicator;