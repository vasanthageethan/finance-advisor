import { useState } from "react";
import { getInsights } from "../api";

export default function InsightsPanel() {
  const [status, setStatus] = useState("idle"); // idle | loading | done | error
  const [insights, setInsights] = useState(null);
  const [error, setError] = useState("");

  async function handleGenerate() {
    setStatus("loading");
    setError("");
    try {
      const data = await getInsights();
      setInsights(data);
      setStatus("done");
    } catch (e) {
      setError(e.message);
      setStatus("error");
    }
  }

  return (
    <div className="rounded-lg border border-hairline bg-surface p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-ink-primary">AI insights</h2>
        <button
          onClick={handleGenerate}
          disabled={status === "loading"}
          className="rounded-md bg-series-1 px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {status === "loading" ? "Generating…" : "Generate AI insights"}
        </button>
      </div>

      {status === "error" && (
        <p className="mt-3 rounded-md border border-hairline bg-plane px-3 py-2 text-sm text-ink-secondary">
          {error}
        </p>
      )}

      {status === "done" && insights && (
        <div className="mt-4 space-y-3">
          <p className="text-sm text-ink-primary">{insights.narrative}</p>
          {insights.flagged_anomalies.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-ink-secondary">Flagged</h3>
              <ul className="mt-1 list-inside list-disc space-y-1 text-sm text-ink-primary">
                {insights.flagged_anomalies.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
