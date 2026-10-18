const BASE_URL = "http://localhost:8000";

// Keep in sync with backend/statement_parsers/__init__.py's PARSERS registry.
export const ACCOUNTS = [
  { value: "chase_credit", label: "Chase Credit Card", fileType: "pdf" },
  { value: "chase_checking", label: "Chase Checking", fileType: "pdf" },
  { value: "capitalone_credit", label: "Capital One Credit Card", fileType: "pdf" },
  { value: "sofi_checking_savings", label: "SoFi Checking & Savings", fileType: "pdf" },
  { value: "other", label: "Other (generic CSV export)", fileType: "csv" },
];

export async function uploadStatement(file, account) {
  const form = new FormData();
  form.append("file", file);
  if (account && account !== "other") form.append("account", account);
  const res = await fetch(`${BASE_URL}/upload`, { method: "POST", body: form });
  if (!res.ok) throw new Error((await res.json()).detail || "Upload failed");
  return res.json();
}

export async function uploadPdfStatement(file, issuer) {
  const form = new FormData();
  form.append("file", file);
  form.append("issuer", issuer);
  const res = await fetch(`${BASE_URL}/upload/statement`, { method: "POST", body: form });
  if (!res.ok) throw new Error((await res.json()).detail || "Upload failed");
  return res.json();
}

export async function getSummary() {
  const res = await fetch(`${BASE_URL}/summary`);
  if (!res.ok) throw new Error("No data yet");
  return res.json();
}

export async function getInsights() {
  const res = await fetch(`${BASE_URL}/insights`);
  if (!res.ok) throw new Error((await res.json()).detail || "Could not generate insights");
  return res.json();
}

export async function getCoverage() {
  const res = await fetch(`${BASE_URL}/coverage`);
  if (!res.ok) throw new Error("No coverage data yet");
  return res.json();
}
