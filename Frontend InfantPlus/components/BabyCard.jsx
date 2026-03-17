import Link from "next/link";
import { memo } from "react";
import RiskIndicator from "./RiskIndicator";

const statusClasses = {
  stable: "bg-[#f2fbf6] border-[#d7ebdf] text-stable",
  warning: "bg-[#fff8ee] border-[#eedfb6] text-warning",
  critical: "bg-[#fff3f3] border-[#f1d1d1] text-critical"
};

function Trend({ direction }) {
  const map = {
    up: { symbol: "+", color: "text-warning" },
    down: { symbol: "-", color: "text-critical" },
    steady: { symbol: "=", color: "text-stable" }
  };
  const item = map[direction] || map.steady;

  return <span className={`text-lg font-semibold ${item.color}`}>{item.symbol}</span>;
}

function BabyCardComponent({ baby }) {
  return (
    <Link
      href={`/baby/${baby.id}`}
      className="group rounded-[28px] border border-[#dbe7ed] bg-white p-5 shadow-panel transition duration-200 hover:-translate-y-1 hover:border-accent/40"
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-slate">Bed {baby.bed}</p>
          <h3 className="mt-2 text-xl font-semibold text-ink">{baby.id}</h3>
          <p className="text-sm text-slate">{baby.name}</p>
        </div>
        <div className={`rounded-full border px-3 py-1 text-xs font-semibold capitalize ${statusClasses[baby.status]}`}>
          {baby.status}
        </div>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3">
        <div className="rounded-2xl bg-[#f7fafc] p-3">
          <p className="text-xs uppercase tracking-[0.22em] text-slate">Heart Rate</p>
          <div className="mt-2 flex items-center justify-between">
            <p className="text-2xl font-semibold">{baby.vitals.heartRate}</p>
            <Trend direction={baby.trend.heartRate} />
          </div>
        </div>
        <div className="rounded-2xl bg-[#f7fafc] p-3">
          <p className="text-xs uppercase tracking-[0.22em] text-slate">SpO2</p>
          <div className="mt-2 flex items-center justify-between">
            <p className="text-2xl font-semibold">{baby.vitals.spo2}%</p>
            <Trend direction={baby.trend.spo2} />
          </div>
        </div>
        <div className="rounded-2xl bg-[#f7fafc] p-3">
          <p className="text-xs uppercase tracking-[0.22em] text-slate">Temp</p>
          <p className="mt-2 text-2xl font-semibold">{baby.vitals.temperature.toFixed(1)} C</p>
        </div>
        <div className="rounded-2xl bg-[#f7fafc] p-3">
          <p className="text-xs uppercase tracking-[0.22em] text-slate">Risk</p>
          <div className="mt-2">
            <RiskIndicator score={baby.riskScore} compact />
          </div>
        </div>
      </div>
    </Link>
  );
}

const BabyCard = memo(BabyCardComponent);

export default BabyCard;
