import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import BPChart from "../../components/BPChart";
import PredictionPanel from "../../components/PredictionPanel";
import RiskIndicator from "../../components/RiskIndicator";
import VitalChart from "../../components/VitalChart";
import { useWebSocket } from "../../hooks/useWebSocket";

const metricCards = (baby) => [
  { label: "Heart Rate", value: `${baby.vitals.heartRate} bpm` },
  { label: "SpO2", value: `${baby.vitals.spo2}%` },
  { label: "Respiration", value: `${baby.vitals.respiration} rpm` },
  { label: "Temperature", value: `${baby.vitals.temperature.toFixed(1)} C` }
];

function DashboardBackIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
      <path d="M11.75 4.5 6.25 10l5.5 5.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M7 10h7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function BabyDetailPage() {
  const router = useRouter();
  const babyId = typeof router.query.id === "string" ? router.query.id : undefined;
  const { data, connectionState } = useWebSocket({ channel: "baby", babyId });
  const baby = data?.baby;

  if (!baby) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-surface px-4 text-ink">
        <div className="rounded-3xl border border-[#dbe7ed] bg-white p-8 shadow-panel">
          <p className="text-lg font-semibold">Loading bedside telemetry...</p>
        </div>
      </main>
    );
  }

  return (
    <>
      <Head>
        <title>{baby.id} | InfantPlus Monitor</title>
      </Head>
      <main className="min-h-screen bg-surface px-4 py-6 text-ink md:px-8">
        <div className="mx-auto max-w-7xl space-y-6">
          <section className="rounded-[32px] border border-white/70 bg-gradient-to-br from-[#fbfdff] to-[#eef4f7] p-6 shadow-panel">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
              <div className="space-y-3">
                <Link
                  href="/"
                  aria-label="Back to Dashboard"
                  data-testid="back-to-dashboard"
                  className="inline-flex w-fit items-center gap-3 rounded-full border border-[#c6dae7] bg-white/95 px-3.5 py-2 text-sm font-semibold text-accent shadow-[0_10px_24px_rgba(42,111,151,0.14)] transition duration-200 hover:-translate-y-0.5 hover:border-[#94bdd4] hover:shadow-[0_14px_30px_rgba(42,111,151,0.2)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#a9cfdf]"
                >
                  <span className="flex h-8 w-8 items-center justify-center rounded-full border border-[#d7e6ee] bg-[#eef7fb]">
                    <DashboardBackIcon />
                  </span>
                  <span>Dashboard</span>
                </Link>
                <div>
                  <h1 className="text-3xl font-semibold">{baby.id} Bedside Monitor</h1>
                  <p className="mt-1 text-sm text-slate">
                    {baby.name} - Bed {baby.bed} - {baby.ageLabel} - Gestation {baby.gestation}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <RiskIndicator score={baby.riskScore} label="Risk Score" />
                <div className="rounded-full border border-[#d4e1e8] bg-white px-4 py-2 text-sm text-slate">
                  Link: {connectionState}
                </div>
              </div>
            </div>
          </section>

          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {metricCards(baby).map((metric) => (
              <div key={metric.label} className="rounded-[26px] border border-[#dbe7ed] bg-white p-5 shadow-panel">
                <p className="text-xs uppercase tracking-[0.25em] text-slate">{metric.label}</p>
                <p className="mt-3 text-3xl font-semibold">{metric.value}</p>
              </div>
            ))}
          </section>

          <section className="grid gap-6 xl:grid-cols-[1.35fr_0.65fr]">
            <div className="space-y-6">
              <VitalChart
                testId="ecg-chart"
                title="ECG Signal vs Forecast"
                color="#2E8B57"
                unit=""
                actualKey="ecg"
                predictedKey="predictedEcg"
                data={baby.ecgChartData || []}
                chartHeightClassName="h-[390px] md:h-[420px]"
                actualStrokeWidth={4}
                predictedStrokeWidth={2.5}
                animationDuration={700}
              />
              <VitalChart
                testId="heart-rate-chart"
                title="Heart Rate vs Time"
                color="#C74C4C"
                unit="bpm"
                actualKey="heartRate"
                predictedKey="predictedHeartRate"
                data={baby.chartData || []}
              />
              <VitalChart
                testId="spo2-chart"
                title="SpO2 vs Time"
                color="#2A6F97"
                unit="%"
                actualKey="spo2"
                predictedKey="predictedSpo2"
                data={baby.chartData || []}
              />
              <BPChart data={baby.bpChartData || []} />
            </div>
            <div className="space-y-6">
              <PredictionPanel prediction={baby.prediction} vitals={baby.vitals} />
              <section className="rounded-[28px] border border-[#dbe7ed] bg-white p-5 shadow-panel">
                <h2 className="text-lg font-semibold">Clinical Snapshot</h2>
                <div className="mt-4 grid gap-3 text-sm text-slate">
                  <div className="rounded-2xl bg-[#f6fafc] p-4">
                    Current status is <span className="font-semibold capitalize text-ink">{baby.status}</span> based on
                    saturation, thermal stability, and heart-rate pattern.
                  </div>
                  <div className="rounded-2xl bg-[#f6fafc] p-4">
                    Last update received at <span className="font-semibold text-ink">{baby.lastUpdated}</span>.
                  </div>
                  <div className="rounded-2xl bg-[#f6fafc] p-4">
                    Bed team priority: <span className="font-semibold text-ink">{baby.prediction.riskLevel}</span>.
                  </div>
                </div>
              </section>
            </div>
          </section>
        </div>
      </main>
    </>
  );
}
