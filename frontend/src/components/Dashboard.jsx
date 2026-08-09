import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from "recharts";
import { getSummary, getInsights } from "../api";

const COLORS = ["#4f46e5", "#059669", "#d97706", "#dc2626", "#0891b2", "#9333ea", "#65a30d"];

export default function Dashboard({ refreshKey }) {
  const [summary, setSummary] = useState(null);
  const [insights, setInsights] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getSummary()
      .then(setSummary)
      .catch((e) => setError(e.message));
  }, [refreshKey]);

  async function loadInsights() {
    try {
      const data = await getInsights();
      setInsights(data);
    } catch (e) {
      setError(e.message);
    }
  }

  if (error) return <p>{error}</p>;
  if (!summary) return <p>Upload a statement to see your spending breakdown.</p>;

  // Reshape monthly summaries into one row per month with category totals as columns.
  const categories = [...new Set(summary.flatMap((m) => m.by_category.map((c) => c.category)))];
  const chartData = summary.map((m) => {
    const row = { month: m.month, total: m.total_spend };
    m.by_category.forEach((c) => (row[c.category] = c.total));
    return row;
  });

  return (
    <div>
      <h2>Spend by category, by month</h2>
      <ResponsiveContainer width="100%" height={400}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="month" />
          <YAxis />
          <Tooltip />
          <Legend />
          {categories.map((cat, i) => (
            <Bar key={cat} dataKey={cat} stackId="a" fill={COLORS[i % COLORS.length]} />
          ))}
        </BarChart>
      </ResponsiveContainer>

      <button onClick={loadInsights} style={{ marginTop: "1rem" }}>
        Generate AI insights
      </button>

      {insights && (
        <div style={{ marginTop: "1rem" }}>
          <h3>Summary</h3>
          <p>{insights.narrative}</p>
          {insights.flagged_anomalies.length > 0 && (
            <>
              <h3>Flagged</h3>
              <ul>
                {insights.flagged_anomalies.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}
