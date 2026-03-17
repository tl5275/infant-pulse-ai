import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import { useEffect, useState } from "react";
import BPChart from "../../components/BPChart";
import LiveStatusBadge from "../../components/LiveStatusBadge";
import PredictionPanel from "../../components/PredictionPanel";
import RiskIndicator from "../../components/RiskIndicator";
import VitalChart from "../../components/VitalChart";
import { useWebSocket } from "../../hooks/useWebSocket";

const MAX_VITAL_POINTS = 60;
const MAX_ECG_POINTS = 96;
const VITAL_POINT_INTERVAL_MS = 1000;
const ECG_POINT_INTERVAL_MS = 50;

const metricCards = (baby) => [
  { label: "Heart Rate", value: `${baby.vitals.heartRate} bpm` },
  { label: "SpO2", value: `${baby.vitals.spo2}%` },
  { label: "Respiration", value: `${baby.vitals.respiration} rpm` },
  { label: "Temperature", value: `${baby.vitals.temperature.toFixed(1)} C` }
];

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function roundValue(value, digits = 1) {
  return Number(Number(value).toFixed(digits));
}

function getNumericValue(value) {
  const nextValue = Number(value);
  return Number.isFinite(nextValue) ? nextValue : null;
}

function extractNumericValues(points, key) {
  return (points || [])
    .map((point) => getNumericValue(point[key]))
    .filter((value) => value !== null);
}

function extractBpActual(points) {
  return (points || [])
    .filter((point) => getNumericValue(point.systolic) !== null && getNumericValue(point.diastolic) !== null)
    .map((point) => ({
      systolic: Number(point.systolic),
      diastolic: Number(point.diastolic)
    }));
}

function extractBpForecast(points) {
  return (points || [])
    .filter(
      (point) =>
        getNumericValue(point.predictedSystolic) !== null && getNumericValue(point.predictedDiastolic) !== null
    )
    .map((point) => ({
      systolic: Number(point.predictedSystolic),
      diastolic: Number(point.predictedDiastolic)
    }));
}

function buildTimestampSeries(values, spacingMs, endAt, limit) {
  const slice = values.slice(-limit);
  if (!slice.length) {
    return [];
  }

  const startAt = endAt - (slice.length - 1) * spacingMs;
  return slice.map((value, index) => ({
    x: startAt + index * spacingMs,
    y: Number(value)
  }));
}

function mapActualForecastSeries({
  points,
  actualKey,
  predictedKey,
  spacingMs,
  endAt,
  limit = MAX_VITAL_POINTS,
  clampRange,
  digits = 1
}) {
  const [minValue, maxValue] = clampRange;
  const actualValues = extractNumericValues(points, actualKey).map((value) => clamp(value, minValue, maxValue));
  const predictedValues = extractNumericValues(points, predictedKey).map((value) => clamp(value, minValue, maxValue));
  const actualSeries = buildTimestampSeries(actualValues, spacingMs, endAt, limit).map((point) => ({
    x: point.x,
    [actualKey]: roundValue(point.y, digits),
    [predictedKey]: null
  }));
  const baseTime = actualSeries[actualSeries.length - 1]?.x || endAt;
  const forecastSeries = predictedValues.map((value, index) => ({
    x: baseTime + (index + 1) * spacingMs,
    [actualKey]: null,
    [predictedKey]: roundValue(value, digits)
  }));

  return [...actualSeries, ...forecastSeries];
}

function buildBpChartData(points, endAt) {
  const actualValues = extractBpActual(points)
    .slice(-MAX_VITAL_POINTS)
    .map((point) => ({
      systolic: clamp(point.systolic, 50, 100),
      diastolic: clamp(point.diastolic, 25, 70)
    }));
  const predictedValues = extractBpForecast(points).map((point) => ({
    systolic: clamp(point.systolic, 50, 100),
    diastolic: clamp(point.diastolic, 25, 70)
  }));

  const actualSeries = actualValues.map((point, index) => ({
    x: endAt - (actualValues.length - 1 - index) * VITAL_POINT_INTERVAL_MS,
    systolic: roundValue(point.systolic, 1),
    predictedSystolic: null,
    diastolic: roundValue(point.diastolic, 1),
    predictedDiastolic: null
  }));
  const baseTime = actualSeries[actualSeries.length - 1]?.x || endAt;
  const forecastSeries = predictedValues.map((point, index) => ({
    x: baseTime + (index + 1) * VITAL_POINT_INTERVAL_MS,
    systolic: null,
    predictedSystolic: roundValue(point.systolic, 1),
    diastolic: null,
    predictedDiastolic: roundValue(point.diastolic, 1)
  }));

  return [...actualSeries, ...forecastSeries];
}

function buildFallbackEcgValues(endAt, count = MAX_ECG_POINTS) {
  const startAt = endAt - (count - 1) * ECG_POINT_INTERVAL_MS;

  return Array.from({ length: count }, (_, index) => {
    const x = startAt + index * ECG_POINT_INTERVAL_MS;
    const phase = x / 100;
    return roundValue(
      clamp(Math.sin(phase) + 0.35 * Math.sin(phase * 2.6) + 0.08 * Math.sin(phase * 8), -2.5, 2.5),
      4
    );
  });
}

function buildEcgChartData(points, endAt) {
  const actualValues = extractNumericValues(points, "ecg")
    .slice(-MAX_ECG_POINTS)
    .map((value) => clamp(value, -2.5, 2.5));
  const predictedValues = extractNumericValues(points, "predictedEcg").map((value) => clamp(value, -2.5, 2.5));
  const sourceValues = actualValues.length ? actualValues : buildFallbackEcgValues(endAt);
  const actualSeries = buildTimestampSeries(sourceValues, ECG_POINT_INTERVAL_MS, endAt, MAX_ECG_POINTS).map((point) => ({
    x: point.x,
    ecg: roundValue(point.y, 4),
    predictedEcg: null
  }));
  const baseTime = actualSeries[actualSeries.length - 1]?.x || endAt;
  const forecastSeries = predictedValues.map((value, index) => ({
    x: baseTime + (index + 1) * ECG_POINT_INTERVAL_MS,
    ecg: null,
    predictedEcg: roundValue(value, 4)
  }));

  return [...actualSeries, ...forecastSeries];
}

function normalizeVitals(vitals) {
  return {
    heartRate: clamp(getNumericValue(vitals?.heartRate) ?? 0, 80, 200),
    spo2: clamp(getNumericValue(vitals?.spo2) ?? 0, 80, 100),
    respiration: clamp(getNumericValue(vitals?.respiration) ?? 0, 20, 90),
    temperature: clamp(getNumericValue(vitals?.temperature) ?? 0, 35, 38)
  };
}

function normalizePrediction(prediction, vitals) {
  if (!prediction) {
    return null;
  }

  return {
    ...prediction,
    predictedHeartRate: clamp(getNumericValue(prediction.predictedHeartRate) ?? vitals.heartRate, 80, 200),
    predictedSpo2: clamp(getNumericValue(prediction.predictedSpo2) ?? vitals.spo2, 80, 100)
  };
}

function handleIncomingData(nextBaby, timestamp = Date.now()) {
  const vitals = normalizeVitals(nextBaby.vitals);
  const prediction = normalizePrediction(nextBaby.prediction, vitals);
  console.log("DATA RECEIVED:", new Date().toISOString());

  return {
    logPayload: {
      babyId: nextBaby.id,
      sourceUpdatedAt: nextBaby.lastUpdated,
      heartRate: vitals.heartRate,
      spo2: vitals.spo2,
      temperature: vitals.temperature
    },
    baby: {
      ...nextBaby,
      vitals,
      prediction: prediction || nextBaby.prediction
    },
    hrData: mapActualForecastSeries({
      points: nextBaby.chartData,
      actualKey: "heartRate",
      predictedKey: "predictedHeartRate",
      spacingMs: VITAL_POINT_INTERVAL_MS,
      endAt: timestamp,
      clampRange: [80, 200]
    }),
    spo2Data: mapActualForecastSeries({
      points: nextBaby.chartData,
      actualKey: "spo2",
      predictedKey: "predictedSpo2",
      spacingMs: VITAL_POINT_INTERVAL_MS,
      endAt: timestamp,
      clampRange: [80, 100]
    }),
    bpData: buildBpChartData(nextBaby.bpChartData, timestamp),
    ecgData: buildEcgChartData(nextBaby.ecgChartData, timestamp)
  };
}

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
  const { data, connectionState, lastUpdatedAt, hasFreshUpdate } = useWebSocket({ channel: "baby", babyId });
  const baby = data?.baby;
  const [liveBaby, setLiveBaby] = useState(null);
  const [ecgData, setEcgData] = useState([]);
  const [hrData, setHrData] = useState([]);
  const [spo2Data, setSpo2Data] = useState([]);
  const [bpData, setBpData] = useState([]);

  useEffect(() => {
    setLiveBaby(null);
    setEcgData([]);
    setHrData([]);
    setSpo2Data([]);
    setBpData([]);
  }, [babyId]);

  useEffect(() => {
    if (!baby) {
      return;
    }

    const nextState = handleIncomingData(baby);
    console.log("DATA FLOW:", nextState.logPayload);
    setLiveBaby(nextState.baby);
    setHrData(nextState.hrData);
    setSpo2Data(nextState.spo2Data);
    setBpData(nextState.bpData);
    setEcgData(nextState.ecgData);
  }, [baby]);
  const currentBaby = liveBaby || baby;

  if (!currentBaby) {
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
        <title>{currentBaby.id} | Infant Pulse Monitor</title>
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
                  <h1 className="text-3xl font-semibold">{currentBaby.id} Bedside Monitor</h1>
                  <p className="mt-1 text-sm text-slate">
                    {currentBaby.name} - Bed {currentBaby.bed} - {currentBaby.ageLabel} - Gestation {currentBaby.gestation}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <LiveStatusBadge
                  connectionState={connectionState}
                  lastUpdatedAt={lastUpdatedAt}
                  hasFreshUpdate={hasFreshUpdate}
                />
                <RiskIndicator score={currentBaby.riskScore} label="Risk Score" />
                <div className="rounded-full border border-[#d4e1e8] bg-white px-4 py-2 text-sm text-slate">
                  Link: {connectionState}
                </div>
              </div>
            </div>
          </section>

          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {metricCards(currentBaby).map((metric) => (
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
                data={ecgData}
                chartHeightClassName="h-[390px] md:h-[420px]"
                actualStrokeWidth={4}
                predictedStrokeWidth={2.5}
                chartKey={`ecg-${ecgData.length}-${ecgData[ecgData.length - 1]?.x || 0}`}
                xKey="x"
                xType="number"
                glow
              />
              <VitalChart
                testId="heart-rate-chart"
                title="Heart Rate vs Time"
                color="#C74C4C"
                unit="bpm"
                actualKey="heartRate"
                predictedKey="predictedHeartRate"
                data={hrData}
                chartKey={`heart-rate-${hrData.length}-${hrData[hrData.length - 1]?.x || 0}`}
                xKey="x"
                xType="number"
              />
              <VitalChart
                testId="spo2-chart"
                title="SpO2 vs Time"
                color="#2A6F97"
                unit="%"
                actualKey="spo2"
                predictedKey="predictedSpo2"
                data={spo2Data}
                chartKey={`spo2-${spo2Data.length}-${spo2Data[spo2Data.length - 1]?.x || 0}`}
                xKey="x"
                xType="number"
              />
              <BPChart
                data={bpData}
                chartKey={`bp-${bpData.length}-${bpData[bpData.length - 1]?.x || 0}`}
                xKey="x"
                xType="number"
              />
            </div>
            <div className="space-y-6">
              <PredictionPanel prediction={currentBaby.prediction} vitals={currentBaby.vitals} />
              <section className="rounded-[28px] border border-[#dbe7ed] bg-white p-5 shadow-panel">
                <h2 className="text-lg font-semibold">Clinical Snapshot</h2>
                <div className="mt-4 grid gap-3 text-sm text-slate">
                  <div className="rounded-2xl bg-[#f6fafc] p-4">
                    Current status is <span className="font-semibold capitalize text-ink">{currentBaby.status}</span>{" "}
                    based on saturation, thermal stability, and heart-rate pattern.
                  </div>
                  <div className="rounded-2xl bg-[#f6fafc] p-4">
                    Last update received at <span className="font-semibold text-ink">{currentBaby.lastUpdated}</span>.
                  </div>
                  <div className="rounded-2xl bg-[#f6fafc] p-4">
                    Bed team priority:{" "}
                    <span className="font-semibold text-ink">{currentBaby.prediction.riskLevel}</span>.
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

export async function getServerSideProps() {
  return {
    props: {}
  };
}
