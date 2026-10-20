import { useMemo, useState } from "react";
import { BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip, LabelList } from "recharts";
import { buildCategoryColorMap, monthBreakdown } from "../lib/categoryColors";

function fmt(n) {
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function fmtCurrency(amount, currency) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 0 }).format(amount);
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const { category, total, color, convertedTotal, convertedCurrency } = payload[0].payload;
  return (
    <div className="rounded-md border border-hairline bg-surface px-3 py-2 text-sm shadow-sm">
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: color }} />
        <span className="text-ink-secondary">{category}</span>
        <span className="ml-auto font-medium tabular-nums text-ink-primary">{fmt(total)}</span>
      </div>
      {convertedTotal != null && (
        <p className="mt-1 text-right text-xs text-ink-muted">≈ {fmtCurrency(convertedTotal, convertedCurrency)}</p>
      )}
    </div>
  );
}

function TableView({ rows }) {
  const hasConverted = rows.some((r) => r.convertedTotal != null);
  return (
    <div className="overflow-x-auto rounded-md border border-hairline">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-hairline bg-plane text-ink-secondary">
            <th scope="col" className="px-3 py-2 font-medium">
              Category
            </th>
            <th scope="col" className="px-3 py-2 font-medium tabular-nums">
              Spend
            </th>
            {hasConverted && (
              <th scope="col" className="px-3 py-2 font-medium tabular-nums">
                Converted
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.category} className="border-b border-hairline last:border-0">
              <td className="px-3 py-2 text-ink-primary">{row.category}</td>
              <td className="px-3 py-2 tabular-nums text-ink-secondary">{fmt(row.total)}</td>
              {hasConverted && (
                <td className="px-3 py-2 tabular-nums text-ink-secondary">
                  {row.convertedTotal != null ? fmtCurrency(row.convertedTotal, row.convertedCurrency) : "—"}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function defaultMonthIndex(summary) {
  for (let i = summary.length - 1; i >= 0; i--) {
    if (!summary[i].is_partial) return i;
  }
  return summary.length - 1; // every month is partial -- just show the latest
}

export default function CategoryBreakdownChart({ summary }) {
  const [showTable, setShowTable] = useState(false);
  const [monthIndex, setMonthIndex] = useState(() => defaultMonthIndex(summary));

  const { colorMap, topCategories } = useMemo(() => buildCategoryColorMap(summary), [summary]);
  const month = summary[monthIndex];
  const rows = useMemo(() => monthBreakdown(month, colorMap, topCategories), [month, colorMap, topCategories]);
  const maxTotal = rows[0]?.total ?? 0;

  return (
    <div className="rounded-lg border border-hairline bg-surface p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-ink-primary">Spend by category</h2>
        <div className="flex items-center gap-2">
          <select
            value={monthIndex}
            onChange={(e) => setMonthIndex(Number(e.target.value))}
            className="rounded-md border border-hairline bg-surface px-2 py-1 text-xs text-ink-primary"
          >
            {summary.map((m, i) => (
              <option key={m.month} value={i}>
                {m.month}
                {m.is_partial ? " (partial)" : ""}
              </option>
            ))}
          </select>
          <button
            onClick={() => setShowTable((v) => !v)}
            className="rounded-md border border-hairline px-2.5 py-1 text-xs text-ink-secondary hover:bg-plane"
          >
            {showTable ? "Show chart" : "Show table"}
          </button>
        </div>
      </div>

      {month.is_partial && (
        <p className="mb-3 flex items-center gap-1.5 text-xs text-ink-secondary">
          <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ backgroundColor: "var(--status-warning)" }} />
          Not every account's {month.month} statement is in yet -- this breakdown is partial.
        </p>
      )}

      {showTable ? (
        <TableView rows={rows} />
      ) : (
        <ResponsiveContainer width="100%" height={Math.max(rows.length * 36, 120)}>
          <BarChart
            data={rows}
            layout="vertical"
            barSize={20}
            margin={{ left: 4, right: 48, top: 4, bottom: 4 }}
          >
            <CartesianGrid horizontal={false} stroke="var(--gridline)" />
            <XAxis type="number" hide domain={[0, maxTotal * 1.15]} />
            <YAxis
              type="category"
              dataKey="category"
              tickLine={false}
              axisLine={false}
              width={150}
              tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "var(--page-plane)" }} />
            <Bar dataKey="total" radius={[0, 4, 4, 0]}>
              {rows.map((row) => (
                <Cell key={row.category} fill={row.color} />
              ))}
              <LabelList
                dataKey="total"
                position="right"
                formatter={fmt}
                style={{ fill: "var(--text-primary)", fontSize: 12, fontWeight: 500 }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
