import Head from "next/head";
import Link from "next/link";
import AlertPopup from "../components/AlertPopup";
import BabyCard from "../components/BabyCard";
import LiveStatusBadge from "../components/LiveStatusBadge";
import NICURoomMap from "../components/NICURoomMap";
import RiskIndicator from "../components/RiskIndicator";
import { useWebSocket } from "../hooks/useWebSocket";

const overviewStats = (babies) => {
  const stable = babies.filter((baby) => baby.status === "stable").length;
  const warning = babies.filter((baby) => baby.status === "warning").length;
  const critical = babies.filter((baby) => baby.status === "critical").length;
  const avgRisk = babies.length
    ? Math.round(babies.reduce((sum, baby) => sum + baby.riskScore, 0) / babies.length)
    : 0;

  return { stable, warning, critical, avgRisk };
};

export default function DashboardPage() {
  const { data, connectionState, lastUpdatedAt, hasFreshUpdate } = useWebSocket({ channel: "overview" });
  const babies = data?.babies || [];
  const alerts = data?.alerts || [];
  const stats = overviewStats(babies);

  return (
    <>
      <Head>
        <title>Infant Pulse NICU Dashboard</title>
      </Head>
      <main className="min-h-screen bg-surface px-4 py-6 text-ink md:px-8">
        <div className="mx-auto max-w-7xl space-y-6">
          <section className="overflow-hidden rounded-[32px] border border-white/60 bg-gradient-to-br from-[#f9fcfe] via-white to-[#eef5f8] p-6 shadow-panel">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-2xl space-y-3">
                <div className="inline-flex items-center rounded-full border border-accent/15 bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.28em] text-accent">
                  Real-time NICU Monitoring
                </div>
                <div>
                  <div className="flex items-center gap-3">
                    <img
                      src="/logo.png"
                      alt="Infant Pulse Logo"
                      className="h-10 w-10 shrink-0 object-contain"
                    />
                    <h1 className="text-2xl font-semibold tracking-tight md:text-4xl">
                      Infant Pulse
                    </h1>
                  </div>
                  <p className="mt-2 max-w-xl text-sm leading-6 text-slate md:text-base">
                    Continuous bedside telemetry, predictive escalation, and family-safe communication in
                    one clinical dashboard.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <div className="rounded-3xl bg-white/90 p-4 shadow-glass">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate">Stable</p>
                  <p className="mt-2 text-3xl font-semibold text-stable">{stats.stable}</p>
                </div>
                <div className="rounded-3xl bg-white/90 p-4 shadow-glass">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate">Warning</p>
                  <p className="mt-2 text-3xl font-semibold text-warning">{stats.warning}</p>
                </div>
                <div className="rounded-3xl bg-white/90 p-4 shadow-glass">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate">Critical</p>
                  <p className="mt-2 text-3xl font-semibold text-critical">{stats.critical}</p>
                </div>
                <div className="rounded-3xl bg-white/90 p-4 shadow-glass">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate">Avg Risk</p>
                  <p className="mt-2 text-3xl font-semibold">{stats.avgRisk}</p>
                </div>
              </div>
            </div>

            <div className="mt-6 flex flex-col gap-4 rounded-[28px] border border-[#dbe7ed] bg-[#fcfeff] p-4 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-4">
                <div className={`h-3 w-3 rounded-full ${connectionState === "open" ? "bg-stable animate-pulse-soft" : "bg-warning"}`} />
                <div>
                  <p className="text-sm font-semibold">Telemetry uplink {connectionState === "open" ? "healthy" : "reconnecting"}</p>
                  <p className="text-xs text-slate">Live refresh every second with auto-reconnect logic.</p>
                </div>
              </div>
              <div className="flex flex-wrap gap-3 text-sm">
                <LiveStatusBadge
                  connectionState={connectionState}
                  lastUpdatedAt={lastUpdatedAt}
                  hasFreshUpdate={hasFreshUpdate}
                />
                <Link href="/parent" className="rounded-full border border-[#d4e1e8] px-4 py-2 text-slate transition hover:border-accent hover:text-accent">
                  Parent View
                </Link>
                <div className="rounded-full bg-ink px-4 py-2 text-white">Shift: Day Watch</div>
              </div>
            </div>
          </section>

          <section className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
            <div className="rounded-[30px] border border-[#dbe7ed] bg-white p-5 shadow-panel">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-semibold">Bedside Overview</h2>
                  <p className="text-sm text-slate">Click any baby card for waveform trends and prediction detail.</p>
                </div>
                <RiskIndicator score={stats.avgRisk} label="Unit Risk" />
              </div>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {babies.map((baby) => (
                  <BabyCard key={baby.id} baby={baby} />
                ))}
              </div>
            </div>

            <div className="space-y-6">
              <NICURoomMap beds={babies} />
              <AlertPopup alerts={alerts} />
            </div>
          </section>
        </div>
      </main>
    </>
  );
}

export async function getServerSideProps() {
  return {
    props: {}
  };
}
