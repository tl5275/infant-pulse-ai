import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import { useEffect, useRef, useState } from "react";
import BPChart from "../../components/BPChart";
import LiveStatusBadge from "../../components/LiveStatusBadge";
import PredictionPanel from "../../components/PredictionPanel";
import RiskIndicator from "../../components/RiskIndicator";
import VitalChart from "../../components/VitalChart";
import { useWebSocket } from "../../hooks/useWebSocket";

const MAX_POINTS = 60;
const VITAL_POINT_INTERVAL_MS = 1000;
const ECG_POINT_INTERVAL_MS = 140;

const metricCards = (baby) => [
  { label: "Heart Rate", value: `${baby.vitals.heartRate} bpm` },
  { label: "SpO2", value: `${baby.vitals.spo2}%` },
  { label: "Respiration", value: `${baby.vitals.respiration} rpm` },
  { label: "Temperature", value: `${baby.vitals.temperature.toFixed(1)} C` }
];

function clampSeries(points, maxPoints = MAX_POINTS) {
  return points.slice(-maxPoints);
}

function roundValue(value, digits = 1) {
  return Number(Number(value).toFixed(digits));
}

function getNumericValue(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
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

function buildSeedSeries(values, spacingMs, endAt = Date.now()) {
  const slice = values.slice(-MAX_POINTS);
  if (!slice.length) {
    return [];
  }

  const startAt = endAt - (slice.length - 1) * spacingMs;
  return slice.map((value, index) => ({
    x: startAt + index * spacingMs,
    y: Number(value)
  }));
}

function buildSeedBpSeries(values, spacingMs, endAt = Date.now()) {
  const slice = values.slice(-MAX_POINTS);
  if (!slice.length) {
    return [];
  }

  const startAt = endAt - (slice.length - 1) * spacingMs;
  return slice.map((point, index) => ({
    x: startAt + index * spacingMs,
    systolic: Number(point.systolic),
    diastolic: Number(point.diastolic)
  }));
}

function buildLineChartData(actualPoints, predictedValues, actualKey, predictedKey, spacingMs, digits = 1) {
  const actualSeries = actualPoints.map((point) => ({
    x: point.x,
    [actualKey]: roundValue(point.y, digits),
    [predictedKey]: null
  }));
  const baseTime = actualPoints[actualPoints.length - 1]?.x || Date.now();
  const forecastSeries = predictedValues.map((value, index) => ({
    x: baseTime + (index + 1) * spacingMs,
    [actualKey]: null,
    [predictedKey]: roundValue(value, digits)
  }));

  return [...actualSeries, ...forecastSeries];
}

function buildBpChartData(actualPoints, predictedPoints, spacingMs, digits = 1) {
  const actualSeries = actualPoints.map((point) => ({
    x: point.x,
    systolic: roundValue(point.systolic, digits),
    predictedSystolic: null,
    diastolic: roundValue(point.diastolic, digits),
    predictedDiastolic: null
  }));
  const baseTime = actualPoints[actualPoints.length - 1]?.x || Date.now();
  const forecastSeries = predictedPoints.map((point, index) => ({
    x: baseTime + (index + 1) * spacingMs,
    systolic: null,
    predictedSystolic: roundValue(point.systolic, digits),
    diastolic: null,
    predictedDiastolic: roundValue(point.diastolic, digits)
  }));

  return [...actualSeries, ...forecastSeries];
}

function generateECG(timestamp) {
  const waveform =
    Math.sin(timestamp / 110) +
    0.45 * Math.sin(timestamp / 24) +
    0.18 * Math.sin(timestamp / 8) +
    Math.random() * 0.08;

  return roundValue(waveform, 4);
}

function getLatestBpPoint(points) {
  const actualPoints = extractBpActual(points);
  return actualPoints[actualPoints.length - 1] || null;
}

function createSnapshotSignature(baby) {
  const latestBp = getLatestBpPoint(baby.bpChartData);

  return [
    baby.lastUpdated,
    baby.vitals.heartRate,
    baby.vitals.spo2,
    baby.vitals.respiration,
    baby.vitals.temperature,
    latestBp?.systolic ?? "na",
    latestBp?.diastolic ?? "na"
  ].join("|");
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
  const [ecgData, setEcgData] = useState([]);
  const [hrData, setHrData] = useState([]);
  const [spo2Data, setSpo2Data] = useState([]);
  const [bpData, setBpData] = useState([]);
  const [ecgForecast, setEcgForecast] = useState([]);
  const [hrForecast, setHrForecast] = useState([]);
  const [spo2Forecast, setSpo2Forecast] = useState([]);
  const [bpForecast, setBpForecast] = useState([]);
  const seededBabyIdRef = useRef(null);
  const lastSnapshotSignatureRef = useRef(null);
  const ecgSamplesRef = useRef([]);
  const ecgCursorRef = useRef(0);

  useEffect(() => {
    seededBabyIdRef.current = null;
    lastSnapshotSignatureRef.current = null;
    ecgSamplesRef.current = [];
    ecgCursorRef.current = 0;
    setEcgData([]);
    setHrData([]);
    setSpo2Data([]);
    setBpData([]);
    setEcgForecast([]);
    setHrForecast([]);
    setSpo2Forecast([]);
    setBpForecast([]);
  }, [babyId]);

  useEffect(() => {
    if (!baby) {
      return;
    }

    const timestamp = Date.now();
    const heartRateHistory = extractNumericValues(baby.chartData, "heartRate");
    const spo2History = extractNumericValues(baby.chartData, "spo2");
    const ecgHistory = extractNumericValues(baby.ecgChartData, "ecg");
    const bloodPressureHistory = extractBpActual(baby.bpChartData);
    const nextHrForecast = extractNumericValues(baby.chartData, "predictedHeartRate");
    const nextSpo2Forecast = extractNumericValues(baby.chartData, "predictedSpo2");
    const nextEcgForecast = extractNumericValues(baby.ecgChartData, "predictedEcg");
    const nextBpForecast = extractBpForecast(baby.bpChartData);
    const snapshotSignature = createSnapshotSignature(baby);
    const currentBpPoint = bloodPressureHistory[bloodPressureHistory.length - 1] || null;

    setHrForecast(nextHrForecast);
    setSpo2Forecast(nextSpo2Forecast);
    setEcgForecast(nextEcgForecast);
    setBpForecast(nextBpForecast);

    if (ecgHistory.length) {
      ecgSamplesRef.current = ecgHistory;
    }

    if (seededBabyIdRef.current !== baby.id) {
      seededBabyIdRef.current = baby.id;
      lastSnapshotSignatureRef.current = snapshotSignature;
      ecgCursorRef.current = 0;
      setHrData(buildSeedSeries(heartRateHistory.length ? heartRateHistory : [baby.vitals.heartRate], VITAL_POINT_INTERVAL_MS, timestamp));
      setSpo2Data(buildSeedSeries(spo2History.length ? spo2History : [baby.vitals.spo2], VITAL_POINT_INTERVAL_MS, timestamp));
      setBpData(buildSeedBpSeries(bloodPressureHistory, VITAL_POINT_INTERVAL_MS, timestamp));
      setEcgData(
        buildSeedSeries(
          ecgHistory.length ? ecgHistory : [generateECG(timestamp - ECG_POINT_INTERVAL_MS), generateECG(timestamp)],
          ECG_POINT_INTERVAL_MS,
          timestamp
        )
      );
      return;
    }

    if (lastSnapshotSignatureRef.current === snapshotSignature) {
      return;
    }

    lastSnapshotSignatureRef.current = snapshotSignature;
    setHrData((previous) => clampSeries([...previous, { x: timestamp, y: baby.vitals.heartRate }]));
    setSpo2Data((previous) => clampSeries([...previous, { x: timestamp, y: baby.vitals.spo2 }]));

    if (currentBpPoint) {
      setBpData((previous) =>
        clampSeries([
          ...previous,
          {
            x: timestamp,
            systolic: currentBpPoint.systolic,
            diastolic: currentBpPoint.diastolic
          }
        ])
      );
    }
  }, [baby]);

  useEffect(() => {
    if (!babyId) {
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      const timestamp = Date.now();
      const samples = ecgSamplesRef.current;
      const nextValue =
        samples.length > 0
          ? Number(samples[ecgCursorRef.current++ % samples.length])
          : generateECG(timestamp);

      setEcgData((previous) =>
        clampSeries([
          ...previous,
          {
            x: timestamp,
            y: nextValue
          }
        ])
      );
    }, ECG_POINT_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [babyId]);

  useEffect(() => {
    console.log("ECG length:", ecgData.length);
  }, [ecgData.length]);

  const ecgChartData = buildLineChartData(ecgData, ecgForecast, "ecg", "predictedEcg", ECG_POINT_INTERVAL_MS, 4);
  const heartRateChartData = buildLineChartData(
    hrData,
    hrForecast,
    "heartRate",
    "predictedHeartRate",
    VITAL_POINT_INTERVAL_MS
  );
  const spo2ChartData = buildLineChartData(
    spo2Data,
    spo2Forecast,
    "spo2",
    "predictedSpo2",
    VITAL_POINT_INTERVAL_MS
  );
  const bloodPressureChartData = buildBpChartData(bpData, bpForecast, VITAL_POINT_INTERVAL_MS);

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
        <title>{baby.id} | Infant Pulse Monitor</title>
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
                <LiveStatusBadge
                  connectionState={connectionState}
                  lastUpdatedAt={lastUpdatedAt}
                  hasFreshUpdate={hasFreshUpdate}
                />
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
                data={ecgChartData}
                chartHeightClassName="h-[390px] md:h-[420px]"
                actualStrokeWidth={4}
                predictedStrokeWidth={2.5}
                animationDuration={700}
                chartKey={`ecg-${ecgData[ecgData.length - 1]?.x || 0}`}
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
                data={heartRateChartData}
                chartKey={`heart-rate-${hrData[hrData.length - 1]?.x || 0}`}
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
                data={spo2ChartData}
                chartKey={`spo2-${spo2Data[spo2Data.length - 1]?.x || 0}`}
                xKey="x"
                xType="number"
              />
              <BPChart
                data={bloodPressureChartData}
                chartKey={`bp-${bpData[bpData.length - 1]?.x || 0}`}
                xKey="x"
                xType="number"
              />
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

export async function getServerSideProps() {
  return {
    props: {}
  };
}
