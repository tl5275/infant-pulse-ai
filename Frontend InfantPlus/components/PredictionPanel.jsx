import { memo } from "react";

const riskTone = {
  LOW: "border-[#d7ebdf] bg-[#f4fbf6] text-stable",
  WARNING: "border-[#f0e1be] bg-[#fffaf0] text-warning",
  CRITICAL: "border-[#f1d1d1] bg-[#fff5f5] text-critical"
};

function PredictionPanelComponent({ prediction, vitals }) {
  return (
    <section className="rounded-[28px] border border-[#dbe7ed] bg-white p-5 shadow-panel">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Predictive Insights</h2>
          <p className="text-sm text-slate">Forecast window based on the latest trend slope and threshold pressure.</p>
        </div>
        <div className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] ${riskTone[prediction.riskLevel]}`}>
          {prediction.riskLevel}
        </div>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2">
        <div className="rounded-2xl bg-[#f6fafc] p-4">
          <p className="text-xs uppercase tracking-[0.22em] text-slate">Predicted Heart Rate</p>
          <p className="mt-2 text-3xl font-semibold text-ink">{prediction.predictedHeartRate} bpm</p>
          <p className="mt-1 text-sm text-slate">Current: {vitals.heartRate} bpm</p>
        </div>
        <div className="rounded-2xl bg-[#f6fafc] p-4">
          <p className="text-xs uppercase tracking-[0.22em] text-slate">Predicted SpO2</p>
          <p className="mt-2 text-3xl font-semibold text-ink">{prediction.predictedSpo2}%</p>
          <p className="mt-1 text-sm text-slate">Current: {vitals.spo2}%</p>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-3 text-sm">
        <div className="rounded-full border border-[#dbe7ed] bg-[#fbfdfe] px-3 py-2 text-slate">
          Anomaly: <span className="font-semibold text-ink">{prediction.anomalyLabel}</span>
        </div>
        <div className="rounded-full border border-[#dbe7ed] bg-[#fbfdfe] px-3 py-2 text-slate">
          Early Warning: <span className="font-semibold text-ink">{prediction.earlyWarning ? "Yes" : "No"}</span>
        </div>
      </div>

      <div className="mt-5 rounded-[24px] border border-[#dbe7ed] bg-[#fbfdfe] p-4">
        <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate">Why this prediction?</h3>
        <div className="mt-3 space-y-3">
          {prediction.reasons.map((reason) => (
            <div key={reason} className="rounded-2xl bg-white p-3 text-sm leading-6 text-ink shadow-sm">
              {reason}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

const PredictionPanel = memo(PredictionPanelComponent);

export default PredictionPanel;
