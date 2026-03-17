import Link from "next/link";
import { memo } from "react";

const bedTone = {
  stable: "border-[#d7ebdf] bg-[#f4fbf6]",
  warning: "border-[#f0e1be] bg-[#fffaf0]",
  critical: "border-[#f1d1d1] bg-[#fff5f5]"
};

function NICURoomMapComponent({ beds }) {
  return (
    <section className="rounded-[30px] border border-[#dbe7ed] bg-white p-5 shadow-panel">
      <div className="mb-4">
        <h2 className="text-xl font-semibold">NICU Digital Twin</h2>
        <p className="text-sm text-slate">Bed positions mapped to live physiological status.</p>
      </div>
      <div className="rounded-[28px] bg-mist bg-grid bg-[size:24px_24px] p-4">
        <div className="grid grid-cols-2 gap-3">
          {beds.map((bed) => (
            <Link
              href={`/baby/${bed.id}`}
              key={bed.id}
              className={`rounded-[24px] border p-4 transition hover:-translate-y-0.5 ${bedTone[bed.status]}`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.22em] text-slate">{bed.bed}</p>
                  <p className="mt-1 text-base font-semibold text-ink">{bed.id}</p>
                </div>
                <span className={`h-3 w-3 rounded-full ${bed.status === "stable" ? "bg-stable" : bed.status === "warning" ? "bg-warning" : "bg-critical"}`} />
              </div>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}

const NICURoomMap = memo(NICURoomMapComponent);

export default NICURoomMap;