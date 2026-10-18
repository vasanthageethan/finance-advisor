import { useEffect, useState } from "react";
import { getSummary } from "../api";
import StatTiles from "./StatTiles";
import SpendTrendChart from "./SpendTrendChart";
import CategoryBreakdownChart from "./CategoryBreakdownChart";
import InsightsPanel from "./InsightsPanel";

export default function Dashboard({ refreshKey }) {
  const [summary, setSummary] = useState(null);
  const [status, setStatus] = useState("loading"); // loading | empty | ready

  useEffect(() => {
    setStatus("loading");
    getSummary()
      .then((data) => {
        setSummary(data);
        setStatus("ready");
      })
      .catch(() => setStatus("empty"));
  }, [refreshKey]);

  if (status === "loading") {
    return <div className="rounded-lg border border-hairline bg-surface p-8 text-sm text-ink-muted">Loading…</div>;
  }

  if (status === "empty") {
    return (
      <div className="rounded-lg border border-dashed border-hairline bg-surface p-8 text-center text-sm text-ink-secondary">
        Upload a statement above to see your spending breakdown.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <StatTiles summary={summary} />
      <SpendTrendChart summary={summary} />
      <CategoryBreakdownChart summary={summary} />
      <InsightsPanel />
    </div>
  );
}
