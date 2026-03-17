import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

function formatTimeTick(value) {
  if (typeof value !== "number") {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    minute: "2-digit",
    second: "2-digit"
  }).format(value);
}

export default function BPChart({
  data,
  chartKey,
  xKey = "label",
  xType = "category",
  xDomain,
  yDomain = [30, 95]
}) {
  const resolvedChartKey = chartKey || `bp-${data?.length || 0}`;
  const isTimeSeries = xType === "number";

  return (
    <section
      data-testid="bp-chart"
      className="rounded-[28px] border border-[#dbe7ed] bg-white p-5 shadow-panel"
    >
      <div className="mb-5 min-h-[72px]">
        <h2 className="text-lg font-semibold">Blood Pressure vs Time</h2>
        <p className="text-sm text-slate">Solid line = live reading, dashed line = next 12 seconds forecast.</p>
      </div>
      <div className="h-[340px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart key={resolvedChartKey} data={data || []} margin={{ top: 10, right: 12, left: -24, bottom: 10 }}>
            <CartesianGrid stroke="#d9e6ec" strokeDasharray="4 4" />
            <XAxis
              dataKey={xKey}
              type={xType}
              domain={isTimeSeries ? (xDomain || ["dataMin", "dataMax"]) : undefined}
              tick={{ fill: "#5B7384", fontSize: 11 }}
              tickFormatter={isTimeSeries ? formatTimeTick : undefined}
            />
            <YAxis tick={{ fill: "#5B7384", fontSize: 11 }} unit="mmHg" domain={yDomain} />
            <Tooltip
              labelFormatter={isTimeSeries ? formatTimeTick : undefined}
              contentStyle={{
                borderRadius: 16,
                border: "1px solid #dbe7ed",
                backgroundColor: "rgba(255,255,255,0.96)"
              }}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="systolic"
              name="Systolic"
              stroke="#8B3D65"
              strokeWidth={3}
              strokeLinecap="round"
              strokeLinejoin="round"
              dot={false}
              isAnimationActive={false}
              animationDuration={500}
              animationEasing="ease-in-out"
            />
            <Line
              type="monotone"
              dataKey="predictedSystolic"
              name="Systolic Forecast"
              stroke="#8B3D65"
              strokeWidth={2}
              strokeDasharray="7 6"
              strokeLinecap="round"
              strokeLinejoin="round"
              dot={false}
              isAnimationActive={false}
              animationDuration={500}
              animationEasing="ease-in-out"
            />
            <Line
              type="monotone"
              dataKey="diastolic"
              name="Diastolic"
              stroke="#D17B42"
              strokeWidth={3}
              strokeLinecap="round"
              strokeLinejoin="round"
              dot={false}
              isAnimationActive={false}
              animationDuration={500}
              animationEasing="ease-in-out"
            />
            <Line
              type="monotone"
              dataKey="predictedDiastolic"
              name="Diastolic Forecast"
              stroke="#D17B42"
              strokeWidth={2}
              strokeDasharray="7 6"
              strokeLinecap="round"
              strokeLinejoin="round"
              dot={false}
              isAnimationActive={false}
              animationDuration={500}
              animationEasing="ease-in-out"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
