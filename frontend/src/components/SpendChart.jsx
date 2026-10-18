import { useMemo, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip } from "recharts";
import { buildCategoryColorMap, toChartRows } from "../lib/categoryColors";

function compactNumber(n) {
  if (n >= 1000) return `${Math.round(n / 100) / 10}K`;
  return `${n}`;
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const rows = payload.filter((p) => p.value).reverse();
  return (
    <div className="rounded-md border border-hairline bg-surface px-3 py-2 text-sm shadow-sm">
      <p className="mb-1.5 font-medium text-ink-primary">{label}</p>
      <dl className="space-y-1">
        {rows.map((p) => (
          <div key={p.dataKey} className="flex items-center gap-2">
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: p.fill }} />
            <dt className="text-ink-secondary">{p.dataKey}</dt>
            <dd className="ml-auto font-medium tabular-nums text-ink-primary">
              ${p.value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function Legend({ series }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm text-ink-secondary">
      {series.map(({ category, color }) => (
        <span key={category} className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: color }} />
          {category}
        </span>
      ))}
    </div>
  );
}

function TableView({ rows, series }) {
  return (
    <div className="overflow-x-auto rounded-md border border-hairline">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-hairline bg-plane text-ink-secondary">
            <th scope="col" className="px-3 py-2 font-medium">
              Month
            </th>
            {series.map(({ category }) => (
              <th key={category} scope="col" className="px-3 py-2 font-medium tabular-nums">
                {category}
              </th>
            ))}
            <th scope="col" className="px-3 py-2 font-medium tabular-nums">
              Total
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.month} className="border-b border-hairline last:border-0">
              <td className="px-3 py-2 text-ink-primary">{row.month}</td>
              {series.map(({ category }) => (
                <td key={category} className="px-3 py-2 tabular-nums text-ink-secondary">
                  {row[category] ? `$${row[category].toLocaleString(undefined, { maximumFractionDigits: 0 })}` : "—"}
                </td>
              ))}
              <td className="px-3 py-2 font-medium tabular-nums text-ink-primary">
                ${row.total.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function SpendChart({ summary }) {
  const [showTable, setShowTable] = useState(false);

  const { colorMap, topCategories } = useMemo(() => buildCategoryColorMap(summary), [summary]);
  const rows = useMemo(() => toChartRows(summary, topCategories), [summary, topCategories]);
  const series = useMemo(
    () => [...colorMap.entries()].map(([category, color]) => ({ category, color })),
    [colorMap]
  );

  return (
    <div className="rounded-lg border border-hairline bg-surface p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-base font-semibold text-ink-primary">Spend by category, by month</h2>
        <button
          onClick={() => setShowTable((v) => !v)}
          className="rounded-md border border-hairline px-2.5 py-1 text-xs text-ink-secondary hover:bg-plane"
        >
          {showTable ? "Show chart" : "Show table"}
        </button>
      </div>

      {showTable ? (
        <TableView rows={rows} series={series} />
      ) : (
        <>
          <ResponsiveContainer width="100%" height={340}>
            <BarChart data={rows} barSize={20} margin={{ left: 4, right: 4, top: 4, bottom: 0 }}>
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
              <Tooltip content={<CustomTooltip />} cursor={{ fill: "var(--page-plane)" }} />
              {series.map(({ category, color }, i) => (
                <Bar
                  key={category}
                  dataKey={category}
                  stackId="spend"
                  fill={color}
                  stroke="var(--surface-1)"
                  strokeWidth={2}
                  radius={i === series.length - 1 ? [4, 4, 0, 0] : 0}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
          <div className="mt-4">
            <Legend series={series} />
          </div>
        </>
      )}
    </div>
  );
}
