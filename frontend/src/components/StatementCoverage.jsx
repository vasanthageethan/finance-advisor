import { useEffect, useState } from "react";
import { ACCOUNTS, getCoverage } from "../api";

function accountLabel(account) {
  return ACCOUNTS.find((a) => a.value === account)?.label ?? account;
}

function StatusPill({ good, label }) {
  const color = good ? "var(--status-good)" : "var(--status-warning)";
  return (
    <span className="inline-flex items-center gap-1.5 text-sm font-medium" style={{ color }}>
      <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}

export default function StatementCoverage({ refreshKey }) {
  const [coverage, setCoverage] = useState(null);
  const [status, setStatus] = useState("loading"); // loading | empty | ready

  useEffect(() => {
    getCoverage()
      .then((data) => {
        setCoverage(data);
        setStatus("ready");
      })
      .catch(() => setStatus("empty"));
  }, [refreshKey]);

  if (status === "loading" || status === "empty") return null;

  return (
    <div className="rounded-lg border border-hairline bg-surface p-5">
      <h2 className="mb-4 text-base font-semibold text-ink-primary">Statement coverage</h2>
      <div className="space-y-4">
        {coverage.accounts.map(({ account, missing_months, covered_months }) => (
          <div key={account} className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:gap-4">
            <span className="w-48 shrink-0 text-sm text-ink-primary">{accountLabel(account)}</span>
            <div className="flex flex-1 flex-wrap items-center gap-2">
              {missing_months.length === 0 ? (
                <StatusPill good label={`Up to date (${covered_months.length} months on file)`} />
              ) : (
                <>
                  <StatusPill label={`${missing_months.length} month${missing_months.length > 1 ? "s" : ""} missing`} />
                  {missing_months.map((m) => (
                    <span
                      key={m}
                      className="rounded-full border border-hairline bg-plane px-2 py-0.5 text-xs text-ink-secondary"
                    >
                      {m}
                    </span>
                  ))}
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
