import { useEffect, useMemo, useState } from "react";
import { getLatestFxRate } from "../api";

function fmtINR(n) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(n);
}

export default function FxRateBanner({ summary }) {
  const [rateInfo, setRateInfo] = useState(null);
  const [status, setStatus] = useState("loading"); // loading | error | ready

  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState("");
  const [result, setResult] = useState(null);

  const categories = useMemo(() => {
    const set = new Set();
    for (const month of summary || []) {
      for (const c of month.by_category) set.add(c.category);
    }
    return [...set].sort();
  }, [summary]);

  useEffect(() => {
    getLatestFxRate("USD", "INR")
      .then((data) => {
        setRateInfo(data);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, []);

  function handleConvert(e) {
    e.preventDefault();
    const value = parseFloat(amount);
    if (!rateInfo || isNaN(value)) return;
    setResult({ category: category || "Amount", converted: value * rateInfo.rate });
  }

  if (status === "loading") return null; // nothing useful to show yet, avoid a layout flash
  if (status === "error") return null; // a down rate service shouldn't block the rest of the dashboard

  return (
    <div className="rounded-lg border border-hairline bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <span className="text-sm text-ink-secondary">Live rate</span>{" "}
          <span className="text-base font-semibold text-ink-primary">
            1 USD = {fmtINR(rateInfo.rate)}
          </span>
          <span className="ml-2 text-xs text-ink-muted">as of {rateInfo.date}</span>
        </div>

        <form onSubmit={handleConvert} className="flex flex-wrap items-center gap-2">
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="rounded-md border border-hairline bg-surface px-2 py-1.5 text-sm text-ink-primary"
          >
            <option value="">Any category</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <input
            type="number"
            step="0.01"
            min="0"
            placeholder="Amount (USD)"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="w-32 rounded-md border border-hairline bg-surface px-2 py-1.5 text-sm text-ink-primary"
          />
          <button
            type="submit"
            className="rounded-md bg-series-1 px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
          >
            Convert
          </button>
        </form>
      </div>

      {result && (
        <p className="mt-3 text-sm text-ink-secondary">
          {result.category}: ${parseFloat(amount).toLocaleString(undefined, { maximumFractionDigits: 2 })} ≈{" "}
          <span className="font-medium text-ink-primary">{fmtINR(result.converted)}</span>
        </p>
      )}
    </div>
  );
}
