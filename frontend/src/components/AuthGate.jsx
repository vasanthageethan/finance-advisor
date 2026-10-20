import { useEffect, useState } from "react";
import { getAuthStatus, getMe, getToken, login, setPassword } from "../auth";
import LandingPage from "./LandingPage.jsx";

function AuthCard({ onBack, children }) {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {onBack && (
          <button
            onClick={onBack}
            className="mb-3 flex items-center gap-1 text-sm text-onGradient-secondary hover:text-onGradient-primary"
          >
            ← Back
          </button>
        )}
        <div className="rounded-lg border border-hairline bg-surface p-6">{children}</div>
      </div>
    </div>
  );
}

function SetupPasswordForm({ onDone, onBack }) {
  const [password, setPasswordValue] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    setSubmitting(true);
    try {
      const data = await setPassword(password);
      onDone(data);
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  return (
    <AuthCard onBack={onBack}>
      <h1 className="text-lg font-semibold text-ink-primary">Set up your password</h1>
      <p className="mt-1 text-sm text-ink-secondary">
        This is a one-time setup for your account. You won't be able to do this again once it's set.
      </p>
      <form onSubmit={handleSubmit} className="mt-4 space-y-3">
        <input
          type="password"
          placeholder="New password"
          value={password}
          onChange={(e) => setPasswordValue(e.target.value)}
          autoFocus
          className="w-full rounded-md border border-hairline bg-surface px-3 py-2 text-sm text-ink-primary"
        />
        <input
          type="password"
          placeholder="Confirm password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          className="w-full rounded-md border border-hairline bg-surface px-3 py-2 text-sm text-ink-primary"
        />
        {error && <p className="text-sm text-status-critical">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-series-1 px-3 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {submitting ? "Setting up…" : "Set password"}
        </button>
      </form>
    </AuthCard>
  );
}

function LoginForm({ onDone, onBack }) {
  const [email, setEmail] = useState("");
  const [password, setPasswordValue] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const data = await login(email, password);
      onDone(data);
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  return (
    <AuthCard onBack={onBack}>
      <h1 className="text-lg font-semibold text-ink-primary">Welcome back</h1>
      <p className="mt-1 text-sm text-ink-secondary">Sign in to continue.</p>
      <form onSubmit={handleSubmit} className="mt-4 space-y-3">
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoFocus
          className="w-full rounded-md border border-hairline bg-surface px-3 py-2 text-sm text-ink-primary"
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPasswordValue(e.target.value)}
          className="w-full rounded-md border border-hairline bg-surface px-3 py-2 text-sm text-ink-primary"
        />
        {error && <p className="text-sm text-status-critical">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-series-1 px-3 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </AuthCard>
  );
}

export default function AuthGate({ children }) {
  const [status, setStatus] = useState("loading"); // loading | landing | setup | login | authenticated
  const [customer, setCustomer] = useState(null);
  const [passwordSet, setPasswordSet] = useState(false);

  useEffect(() => {
    getAuthStatus()
      .then(async ({ password_set }) => {
        setPasswordSet(password_set);
        if (password_set && getToken()) {
          try {
            const me = await getMe();
            setCustomer(me);
            setStatus("authenticated");
            return;
          } catch {
            // fall through to the landing page
          }
        }
        setStatus("landing");
      })
      .catch(() => setStatus("landing"));
  }, []);

  function handleAuthed({ customer_id, name }) {
    setCustomer({ customer_id, name });
    setStatus("authenticated");
  }

  if (status === "loading") {
    return (
      <AuthCard>
        <p className="text-sm text-ink-muted">Loading…</p>
      </AuthCard>
    );
  }
  if (status === "landing") {
    return <LandingPage onContinue={() => setStatus(passwordSet ? "login" : "setup")} />;
  }
  if (status === "setup") return <SetupPasswordForm onDone={handleAuthed} onBack={() => setStatus("landing")} />;
  if (status === "login") return <LoginForm onDone={handleAuthed} onBack={() => setStatus("landing")} />;
  return children(customer);
}
