import { useState } from "react";
import { uploadStatement } from "../api";

export default function UploadForm({ onUploaded }) {
  const [status, setStatus] = useState("");

  async function handleChange(e) {
    const file = e.target.files[0];
    if (!file) return;
    setStatus("Uploading and categorizing...");
    try {
      const transactions = await uploadStatement(file);
      setStatus(`Loaded ${transactions.length} transactions`);
      onUploaded();
    } catch (err) {
      setStatus(`Error: ${err.message}`);
    }
  }

  return (
    <div style={{ marginBottom: "1.5rem" }}>
      <label>
        Upload a statement CSV (columns: date, description, amount):{" "}
        <input type="file" accept=".csv" onChange={handleChange} />
      </label>
      {status && <p>{status}</p>}
    </div>
  );
}
