import HeroVisual from "./HeroVisual.jsx";

const FEATURES = [
  {
    title: "Multi-bank statement parsing",
    body: "Upload real Chase, Capital One, and SoFi PDF statements — each one reconciled against its own declared total before anything is trusted.",
  },
  {
    title: "Three-tier categorization",
    body: "Free keyword rules first, a local model for the rest, Claude (or a local LLM) reserved for the one tier that actually needs real reasoning.",
  },
  {
    title: "AI-generated insights",
    body: "A written trend narrative and anomaly flags, generated locally by default — no API key required to get started.",
  },
  {
    title: "Statement coverage tracking",
    body: "A dashboard card flags any account missing a recent month's statement, so a gap doesn't silently skew your spend totals.",
  },
];

export default function LandingPage({ onContinue }) {
  return (
    <div className="min-h-screen px-4 py-16 sm:py-24">
      <div className="mx-auto max-w-2xl text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-onGradient-primary sm:text-4xl">
          Personal Finance Advisor
        </h1>
        <p className="mx-auto mt-4 max-w-lg text-base text-onGradient-secondary">
          Spend tracking and AI-generated trend insights across your own bank and card statements — parsed,
          categorized, and reconciled locally.
        </p>
        <button
          onClick={onContinue}
          className="mt-8 rounded-md bg-series-1 px-6 py-2.5 text-sm font-medium text-white hover:opacity-90"
        >
          Sign in
        </button>
      </div>

      <div className="mx-auto mt-12 max-w-md">
        <HeroVisual />
      </div>

      <div className="mx-auto mt-12 grid max-w-3xl grid-cols-1 gap-4 sm:grid-cols-2">
        {FEATURES.map((f) => (
          <div key={f.title} className="rounded-lg border border-hairline bg-surface p-5">
            <h2 className="text-sm font-semibold text-ink-primary">{f.title}</h2>
            <p className="mt-1.5 text-sm text-ink-secondary">{f.body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
