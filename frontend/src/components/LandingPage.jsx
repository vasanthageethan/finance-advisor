import HeroVisual from "./HeroVisual.jsx";

const ICON_PROPS = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: "1.8",
  strokeLinecap: "round",
  strokeLinejoin: "round",
  className: "h-5 w-5",
};

function BankIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M3 10l9-6 9 6" />
      <path d="M5 10v9M19 10v9M9 19v-6M15 19v-6" />
      <path d="M3 19h18" />
    </svg>
  );
}

function LayersIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M12 3l9 5-9 5-9-5 9-5z" />
      <path d="M3 13l9 5 9-5" />
    </svg>
  );
}

function SparkIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M12 3v5M12 16v5M3 12h5M16 12h5M6 6l3 3M18 18l-3-3M6 18l3-3M18 6l-3 3" />
    </svg>
  );
}

function FlagIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M5 21V4" />
      <path d="M5 4h13l-3 4 3 4H5" />
    </svg>
  );
}

const FEATURES = [
  { icon: BankIcon, color: "var(--series-1)", title: "Multi-bank parsing", body: "Chase, Cap One, SoFi" },
  { icon: LayersIcon, color: "var(--series-2)", title: "Smart tiering", body: "Rules → model → LLM" },
  { icon: SparkIcon, color: "var(--series-3)", title: "Local AI insights", body: "No API key needed" },
  { icon: FlagIcon, color: "var(--series-4)", title: "Coverage tracking", body: "Never miss a statement" },
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

      <div className="mx-auto mt-12 grid max-w-3xl grid-cols-2 gap-3 sm:grid-cols-4">
        {FEATURES.map(({ icon: Icon, color, title, body }) => (
          <div
            key={title}
            className="flex flex-col items-center rounded-lg border border-hairline bg-surface p-4 text-center"
          >
            <span
              className="mb-2 flex h-9 w-9 items-center justify-center rounded-full"
              style={{ color, backgroundColor: "color-mix(in srgb, " + color + " 15%, transparent)" }}
            >
              <Icon />
            </span>
            <h2 className="text-sm font-semibold text-ink-primary">{title}</h2>
            <p className="mt-0.5 text-xs text-ink-secondary">{body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
