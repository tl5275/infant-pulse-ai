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
  testId
}) {
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
          <LineChart data={data || []} margin={{ top: 10, right: 12, left: -24, bottom: 10 }}>
            <CartesianGrid stroke="#d9e6ec" strokeDasharray="4 4" />
            <XAxis dataKey="label" tick={{ fill: "#5B7384", fontSize: 11 }} />
            <YAxis tick={{ fill: "#5B7384", fontSize: 11 }} unit={unit} />
            <Tooltip
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
              name="Actual"
              stroke={color}
              strokeWidth={actualStrokeWidth}
              strokeLinecap="round"
              strokeLinejoin="round"
              dot={false}
              isAnimationActive
              animationDuration={animationDuration}
              animationEasing="ease-in-out"
            />
            <Line
              type="monotone"
              dataKey={predictedKey}
              name="Predicted"
              stroke={color}
              strokeWidth={predictedStrokeWidth}
              strokeDasharray="7 6"
              strokeLinecap="round"
              strokeLinejoin="round"
              dot={false}
              isAnimationActive
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
