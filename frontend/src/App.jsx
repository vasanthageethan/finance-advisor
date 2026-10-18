import { useState } from "react";
import AuthGate from "./components/AuthGate.jsx";
import UploadForm from "./components/UploadForm.jsx";
import Dashboard from "./components/Dashboard.jsx";
import { logout } from "./auth";

export default function App() {
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <AuthGate>
      {(customer) => {
        const firstName = customer.name.split(" ")[0];
        return (
          <div className="min-h-screen">
            <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
              <header className="mb-6 flex items-start justify-between gap-4">
                <div>
                  <h1 className="text-xl font-semibold text-onGradient-primary">Personal Finance Advisor</h1>
                  <p className="mt-1 text-sm text-onGradient-secondary">
                    Spend tracking and AI-generated trend insights.
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <span className="text-sm text-onGradient-primary">Hello {firstName}</span>
                  <button
                    onClick={async () => {
                      await logout();
                      window.location.reload();
                    }}
                    className="rounded-md border border-hairline px-2.5 py-1 text-xs text-onGradient-secondary hover:bg-white/5"
                  >
                    Log out
                  </button>
                </div>
              </header>
              <div className="space-y-6">
                <UploadForm onUploaded={() => setRefreshKey((k) => k + 1)} />
                <Dashboard refreshKey={refreshKey} />
              </div>
            </div>
          </div>
        );
      }}
    </AuthGate>
  );
}
