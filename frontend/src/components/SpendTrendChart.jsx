import { useMemo, useState } from "react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip } from "recharts";

function compactNumber(n) {
  if (n >= 1000) return `${Math.round(n / 100) / 10}K`;
  return `${n}`;
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-hairline bg-surface px-3 py-2 text-sm shadow-sm">
      <p className="text-ink-secondary">{label}</p>
      <p className="font-medium tabular-nums text-ink-primary">
        ${payload[0].value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
      </p>
    </div>
  );
}

function TableView({ rows }) {
  return (
    <div className="overflow-x-auto rounded-md border border-hairline">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-hairline bg-plane text-ink-secondary">
            <th scope="col" className="px-3 py-2 font-medium">
              Month
            </th>
            <th scope="col" className="px-3 py-2 font-medium tabular-nums">
              Total spend
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.month} className="border-b border-hairline last:border-0">
              <td className="px-3 py-2 text-ink-primary">{row.month}</td>
              <td className="px-3 py-2 tabular-nums text-ink-secondary">
                ${row.total.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function SpendTrendChart({ summary }) {
  const [showTable, setShowTable] = useState(false);
  const rows = useMemo(() => summary.map((m) => ({ month: m.month, total: m.total_spend })), [summary]);

  return (
    <div className="rounded-lg border border-hairline bg-surface p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-base font-semibold text-ink-primary">Total spend over time</h2>
        <button
          onClick={() => setShowTable((v) => !v)}
          className="rounded-md border border-hairline px-2.5 py-1 text-xs text-ink-secondary hover:bg-plane"
        >
          {showTable ? "Show chart" : "Show table"}
        </button>
      </div>

      {showTable ? (
        <TableView rows={rows} />
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={rows} margin={{ left: 4, right: 24, top: 8, bottom: 0 }}>
            <defs>
              <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--series-1)" stopOpacity={0.14} />
                <stop offset="100%" stopColor="var(--series-1)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke="var(--gridline)" />
            <XAxis
              dataKey="month"
              tickLine={false}
              axisLine={{ stroke: "var(--baseline)" }}
              tick={{ fill: "var(--text-muted)", fontSize: 12 }}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              tickFormatter={compactNumber}
              tick={{ fill: "var(--text-muted)", fontSize: 12 }}
              width={36}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ stroke: "var(--baseline)", strokeWidth: 1 }} />
            <Area
              type="monotone"
              dataKey="total"
              stroke="var(--series-1)"
              strokeWidth={2}
              fill="url(#trendFill)"
              dot={{ r: 3, fill: "var(--series-1)", stroke: "var(--surface-1)", strokeWidth: 2 }}
              activeDot={{ r: 5, fill: "var(--series-1)", stroke: "var(--surface-1)", strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
