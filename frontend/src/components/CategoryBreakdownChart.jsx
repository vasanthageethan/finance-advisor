import { useMemo, useState } from "react";
import { BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip, LabelList } from "recharts";
import { buildCategoryColorMap, monthBreakdown } from "../lib/categoryColors";

function fmt(n) {
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const { category, total, color } = payload[0].payload;
  return (
    <div className="flex items-center gap-2 rounded-md border border-hairline bg-surface px-3 py-2 text-sm shadow-sm">
      <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: color }} />
      <span className="text-ink-secondary">{category}</span>
      <span className="ml-auto font-medium tabular-nums text-ink-primary">{fmt(total)}</span>
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
              Category
            </th>
            <th scope="col" className="px-3 py-2 font-medium tabular-nums">
              Spend
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.category} className="border-b border-hairline last:border-0">
              <td className="px-3 py-2 text-ink-primary">{row.category}</td>
              <td className="px-3 py-2 tabular-nums text-ink-secondary">{fmt(row.total)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function CategoryBreakdownChart({ summary }) {
  const [showTable, setShowTable] = useState(false);
  const [monthIndex, setMonthIndex] = useState(summary.length - 1);

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
