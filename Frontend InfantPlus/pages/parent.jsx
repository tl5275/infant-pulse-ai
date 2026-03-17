import Head from "next/head";
import Link from "next/link";
import LiveStatusBadge from "../components/LiveStatusBadge";
import { useRouter } from "next/router";
import { useEffect, useState } from "react";
import { useWebSocket } from "../hooks/useWebSocket";

function ParentMessage({ baby }) {
  const tone = baby.status === "stable" ? "stable" : baby.status === "warning" ? "warning" : "critical";
  const messages = {
    stable: "Your baby is stable and being monitored continuously.",
    warning: "Your baby is under close observation and the care team is reviewing changes.",
    critical: "Your baby needs urgent clinical attention. The NICU team is actively responding."
  };

  return (
    <div
      className={`rounded-[28px] p-6 shadow-panel ${
        tone === "stable"
          ? "border border-[#d5eadf] bg-[#f5fbf7]"
          : tone === "warning"
            ? "border border-[#f0e1be] bg-[#fffaf0]"
            : "border border-[#f3d3d3] bg-[#fff5f5]"
      }`}
    >
      <p className="text-xs uppercase tracking-[0.28em] text-slate">Family Update</p>
      <h1 className="mt-3 text-3xl font-semibold text-ink">{messages[tone]}</h1>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-slate">
        Bed {baby.bed} is connected to live NICU monitoring. The care team is watching oxygen, breathing, and comfort
        indicators in real time.
      </p>
    </div>
  );
}

export default function ParentPage() {
  const router = useRouter();
  const routeSelectedId = typeof router.query.id === "string" ? router.query.id : null;
  const { data, connectionState, lastUpdatedAt, hasFreshUpdate } = useWebSocket({ channel: "overview" });
  const babies = data?.babies || [];
  const [selectedBabyId, setSelectedBabyId] = useState(routeSelectedId);

  useEffect(() => {
    if (routeSelectedId) {
      setSelectedBabyId(routeSelectedId);
    }
  }, [routeSelectedId]);

  useEffect(() => {
    if (!babies.length) {
      return;
    }

    setSelectedBabyId((current) => {
      if (current && babies.some((baby) => baby.id === current)) {
        return current;
      }

      return babies[0].id;
    });
  }, [babies]);

  const selectedBaby = babies.find((baby) => baby.id === selectedBabyId) || babies[0];

  function handleSelectBaby(nextBabyId) {
    setSelectedBabyId(nextBabyId);
    router.replace(
      {
        pathname: "/parent",
        query: { id: nextBabyId }
      },
      undefined,
      { shallow: true }
    );
  }

  if (!selectedBaby) {
    return null;
  }

  return (
    <>
      <Head>
        <title>Parent View | Infant Pulse</title>
      </Head>
      <main className="min-h-screen bg-surface px-4 py-8 text-ink md:px-8">
        <div className="mx-auto max-w-5xl space-y-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="space-y-2">
              <p className="text-xs uppercase tracking-[0.24em] text-slate">Parent Access</p>
              <p className="text-sm text-slate">
                Showing updates for <span className="font-semibold text-ink">{selectedBaby.id}</span>. Choose any baby
                card below to switch views instantly.
              </p>
              <p className="text-xs text-slate">
                Live feed status: <span className="font-semibold capitalize text-ink">{connectionState}</span>
              </p>
              <LiveStatusBadge
                connectionState={connectionState}
                lastUpdatedAt={lastUpdatedAt}
                hasFreshUpdate={hasFreshUpdate}
              />
            </div>
            <Link href="/" className="rounded-full border border-[#d4e1e8] px-4 py-2 text-sm text-slate transition hover:border-accent hover:text-accent">
              Back to Dashboard
            </Link>
          </div>

          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {babies.map((baby) => {
              const isSelected = baby.id === selectedBaby.id;

              return (
                <button
                  key={baby.id}
                  type="button"
                  onClick={() => handleSelectBaby(baby.id)}
                  className={`rounded-[24px] border p-4 text-left shadow-panel transition ${
                    isSelected
                      ? "border-accent bg-white ring-2 ring-accent/20"
                      : "border-[#dbe7ed] bg-white hover:border-accent/50"
                  }`}
                >
                  <p className="text-xs uppercase tracking-[0.22em] text-slate">{baby.bed}</p>
                  <p className="mt-2 text-lg font-semibold text-ink">{baby.id}</p>
                  <p className="text-sm text-slate">{baby.name}</p>
                </button>
              );
            })}
          </section>

          <ParentMessage baby={selectedBaby} />

          <section className="grid gap-4 md:grid-cols-3">
            <div className="rounded-[26px] border border-[#dbe7ed] bg-white p-5 shadow-panel">
              <p className="text-xs uppercase tracking-[0.2em] text-slate">Heart Rate</p>
              <p className="mt-3 text-3xl font-semibold">{selectedBaby.vitals.heartRate} bpm</p>
            </div>
            <div className="rounded-[26px] border border-[#dbe7ed] bg-white p-5 shadow-panel">
              <p className="text-xs uppercase tracking-[0.2em] text-slate">Oxygen</p>
              <p className="mt-3 text-3xl font-semibold">{selectedBaby.vitals.spo2}%</p>
            </div>
            <div className="rounded-[26px] border border-[#dbe7ed] bg-white p-5 shadow-panel">
              <p className="text-xs uppercase tracking-[0.2em] text-slate">Temperature</p>
              <p className="mt-3 text-3xl font-semibold">{selectedBaby.vitals.temperature.toFixed(1)} C</p>
            </div>
          </section>

          <section className="rounded-[28px] border border-[#dbe7ed] bg-white p-6 shadow-panel">
            <h2 className="text-xl font-semibold">Today's Reassurance</h2>
            <p className="mt-3 text-sm leading-6 text-slate">
              Your baby's bedside monitor is sharing updates with the NICU team every second. If anything changes,
              clinicians are notified immediately.
            </p>
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
