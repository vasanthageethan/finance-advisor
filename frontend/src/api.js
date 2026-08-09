const BASE_URL = "http://localhost:8000";

export async function uploadStatement(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE_URL}/upload`, { method: "POST", body: form });
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
  if (!res.ok) throw new Error("Could not generate insights");
  return res.json();
}
