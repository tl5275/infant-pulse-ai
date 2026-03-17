const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(__dirname, "..");
const babyPagePath = path.join(repoRoot, "Frontend InfantPlus", "pages", "baby", "[id].jsx");
const bpChartPath = path.join(repoRoot, "Frontend InfantPlus", "components", "BPChart.js");
const vitalChartPath = path.join(repoRoot, "Frontend InfantPlus", "components", "VitalChart.jsx");

function readFile(filePath) {
  return fs.readFileSync(filePath, "utf8");
}

function runCheck(name, callback) {
  callback();
  console.log(`PASS ${name}`);
}

runCheck("ECG chart is the first bedside graph", () => {
  const babyPage = readFile(babyPagePath);
  const ecgIndex = babyPage.indexOf('title="ECG Signal vs Forecast"');
  const heartRateIndex = babyPage.indexOf('title="Heart Rate vs Time"');
  const spo2Index = babyPage.indexOf('title="SpO2 vs Time"');
  const bpIndex = babyPage.indexOf("<BPChart");

  assert.ok(ecgIndex !== -1, "Expected ECG chart JSX to be present");
  assert.ok(heartRateIndex !== -1, "Expected Heart Rate chart JSX to be present");
  assert.ok(spo2Index !== -1, "Expected SpO2 chart JSX to be present");
  assert.ok(bpIndex !== -1, "Expected BP chart JSX to be present");
  assert.ok(ecgIndex < heartRateIndex, "Expected ECG chart to render before Heart Rate");
  assert.ok(heartRateIndex < spo2Index, "Expected Heart Rate chart to render before SpO2");
  assert.ok(spo2Index < bpIndex, "Expected SpO2 chart to render before BP");
});

runCheck("ECG and BP chart components expose the expected hooks", () => {
  const babyPage = readFile(babyPagePath);
  const bpChart = readFile(bpChartPath);
  const vitalChart = readFile(vitalChartPath);

  assert.match(babyPage, /testId="ecg-chart"/);
  assert.match(vitalChart, /data-testid=\{testId\}/);
  assert.match(bpChart, /data-testid="bp-chart"/);
  assert.match(bpChart, /dataKey="systolic"/);
  assert.match(bpChart, /dataKey="diastolic"/);
  assert.match(bpChart, /dataKey="predictedSystolic"/);
  assert.match(bpChart, /dataKey="predictedDiastolic"/);
});

runCheck("Back button exists with the upgraded dashboard label", () => {
  const babyPage = readFile(babyPagePath);

  assert.match(babyPage, /data-testid="back-to-dashboard"/);
  assert.match(babyPage, /aria-label="Back to Dashboard"/);
  assert.match(babyPage, /<span>Dashboard<\/span>/);
});

console.log("UI source checks passed.");
