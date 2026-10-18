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
    <div style={{ marginBottom: "1.5rem" }}>
      <label>
        Account:{" "}
        <select value={accountValue} onChange={(e) => setAccountValue(e.target.value)}>
          {ACCOUNTS.map((a) => (
            <option key={a.value} value={a.value}>
              {a.label}
            </option>
          ))}
        </select>
      </label>
      <div style={{ marginTop: "0.5rem" }}>
        <label>
          Upload statement ({account.fileType === "pdf" ? "PDF" : "CSV: date, description, amount"}):{" "}
          <input
            key={accountValue /* reset the file input when the account changes */}
            type="file"
            accept={account.fileType === "pdf" ? ".pdf" : ".csv"}
            onChange={handleChange}
          />
        </label>
      </div>
      {status && <p>{status}</p>}
    </div>
  );
}
