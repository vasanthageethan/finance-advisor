import { useState } from "react";
import UploadForm from "./components/UploadForm.jsx";
import Dashboard from "./components/Dashboard.jsx";

export default function App() {
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div className="min-h-screen">
      <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
        <header className="mb-6">
          <h1 className="text-xl font-semibold text-onGradient-primary">Personal Finance Advisor</h1>
          <p className="mt-1 text-sm text-onGradient-secondary">Spend tracking and AI-generated trend insights.</p>
        </header>
        <div className="space-y-6">
          <UploadForm onUploaded={() => setRefreshKey((k) => k + 1)} />
          <Dashboard refreshKey={refreshKey} />
        </div>
      </div>
    </div>
  );
}
