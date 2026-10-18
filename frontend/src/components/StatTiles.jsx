function fmt(n) {
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function StatTile({ label, value, sub }) {
  return (
    <div className="rounded-lg border border-hairline bg-surface p-4">
      <p className="text-sm text-ink-secondary">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-ink-primary">{value}</p>
      {sub && <p className="mt-1 text-sm text-ink-muted">{sub}</p>}
    </div>
  );
}

export default function StatTiles({ summary }) {
  const latest = summary[summary.length - 1];
  const prior = summary[summary.length - 2];
  const delta = prior ? latest.total_spend - prior.total_spend : null;
  const topCategory = [...latest.by_category].sort((a, b) => b.total - a.total)[0];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <StatTile
        label={`Spend in ${latest.month}`}
        value={fmt(latest.total_spend)}
        sub={delta !== null ? `${delta >= 0 ? "+" : "-"}${fmt(Math.abs(delta))} vs ${prior.month}` : undefined}
      />
      <StatTile
        label="Top category"
        value={topCategory ? topCategory.category : "—"}
        sub={topCategory ? `${fmt(topCategory.total)} (${topCategory.pct_of_spend}% of spend)` : undefined}
      />
      <StatTile label="Months of data" value={summary.length} sub={`${summary[0].month} – ${latest.month}`} />
    </div>
  );
}
