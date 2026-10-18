import { useState } from "react";
import { ACCOUNTS, uploadPdfStatement, uploadStatement } from "../api";

export default function UploadForm({ onUploaded }) {
  const [accountValue, setAccountValue] = useState(ACCOUNTS[0].value);
  const [status, setStatus] = useState("");

  const account = ACCOUNTS.find((a) => a.value === accountValue);

  async function handleChange(e) {
    const file = e.target.files[0];
    if (!file) return;
    setStatus(`Uploading and categorizing (${account.label})...`);
    try {
      const transactions =
        account.fileType === "pdf"
          ? await uploadPdfStatement(file, account.value)
          : await uploadStatement(file, account.value);
      setStatus(`Loaded ${transactions.length} transactions for ${account.label}`);
      onUploaded();
    } catch (err) {
      setStatus(`Error: ${err.message}`);
    } finally {
      e.target.value = ""; // allow re-selecting the same file after a fix
    }
  }

  return (
    <div className="rounded-lg border border-hairline bg-surface p-5">
      <div className="flex flex-wrap items-end gap-4">
        <label className="flex flex-col gap-1 text-sm text-ink-secondary">
          Account
          <select
            value={accountValue}
            onChange={(e) => setAccountValue(e.target.value)}
            className="rounded-md border border-hairline bg-surface px-2.5 py-1.5 text-sm text-ink-primary"
          >
            {ACCOUNTS.map((a) => (
              <option key={a.value} value={a.value}>
                {a.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm text-ink-secondary">
          Upload statement ({account.fileType === "pdf" ? "PDF" : "CSV"})
          <input
            key={accountValue /* reset the file input when the account changes */}
            type="file"
            accept={account.fileType === "pdf" ? ".pdf" : ".csv"}
            onChange={handleChange}
            className="text-sm text-ink-primary file:mr-3 file:rounded-md file:border-0 file:bg-series-1 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:opacity-90"
          />
        </label>
      </div>
      {status && <p className="mt-3 text-sm text-ink-secondary">{status}</p>}
    </div>
  );
}
