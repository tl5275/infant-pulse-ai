import { memo } from "react";
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

function VitalChartComponent({
  title,
  color,
  unit,
  actualKey,
  predictedKey,
  data,
  description = "Solid line = live reading, dashed line = next 12 seconds forecast.",
  chartHeightClassName = "h-[340px]",
  actualStrokeWidth = 3,
  predictedStrokeWidth = 2,
  animationDuration = 450,
  testId,
  chartKey,
  xKey = "label",
  xType = "category",
  xDomain,
  yDomain,
  actualName = "Actual",
  predictedName = "Predicted",
  glow = false
}) {
  const resolvedChartKey = chartKey || `${title}-${data?.length || 0}`;
  const isTimeSeries = xType === "number";

  return (
    <section
      data-testid={testId}
      className="rounded-[28px] border border-[#dbe7ed] bg-white p-5 shadow-panel"
    >
      <div className="mb-5 min-h-[72px]">
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="text-sm text-slate">{description}</p>
      </div>
      <div className={chartHeightClassName}>
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
            <YAxis tick={{ fill: "#5B7384", fontSize: 11 }} unit={unit} domain={yDomain} />
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
              dataKey={actualKey}
              name={actualName}
              stroke={color}
              strokeWidth={actualStrokeWidth}
              strokeLinecap="round"
              strokeLinejoin="round"
              style={glow ? { filter: `drop-shadow(0 0 8px ${color})` } : undefined}
              dot={false}
              isAnimationActive={false}
              animationDuration={animationDuration}
              animationEasing="ease-in-out"
            />
            <Line
              type="monotone"
              dataKey={predictedKey}
              name={predictedName}
              stroke={color}
              strokeWidth={predictedStrokeWidth}
              strokeDasharray="7 6"
              strokeLinecap="round"
              strokeLinejoin="round"
              dot={false}
              isAnimationActive={false}
              animationDuration={animationDuration}
              animationEasing="ease-in-out"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

const VitalChart = memo(VitalChartComponent);

export default VitalChart;
