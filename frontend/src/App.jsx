import { useState } from "react";
import UploadForm from "./components/UploadForm.jsx";
import Dashboard from "./components/Dashboard.jsx";

export default function App() {
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div style={{ maxWidth: 900, margin: "2rem auto", fontFamily: "sans-serif" }}>
      <h1>Personal Finance Advisor</h1>
      <UploadForm onUploaded={() => setRefreshKey((k) => k + 1)} />
      <Dashboard refreshKey={refreshKey} />
    </div>
  );
}
