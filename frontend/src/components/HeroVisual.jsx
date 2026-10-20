// A small illustrative preview of the dashboard itself -- bars + a trend
// line in the app's own categorical palette, animating in once on mount.
// Deliberately abstract (not real data): it's here to look professional
// and hint at what the product does, not to inform anyone of anything.
const BARS = [
  { x: 24, height: 60, color: "var(--series-1)" },
  { x: 76, height: 92, color: "var(--series-2)" },
  { x: 128, height: 48, color: "var(--series-3)" },
  { x: 180, height: 110, color: "var(--series-4)" },
  { x: 232, height: 76, color: "var(--series-5)" },
  { x: 284, height: 100, color: "var(--series-6)" },
  { x: 336, height: 64, color: "var(--series-7)" },
];

const BASELINE = 164;
const BAR_WIDTH = 28;

const LINE_POINTS = [
  [24 + BAR_WIDTH / 2, 120],
  [76 + BAR_WIDTH / 2, 88],
  [128 + BAR_WIDTH / 2, 132],
  [180 + BAR_WIDTH / 2, 60],
  [232 + BAR_WIDTH / 2, 104],
  [284 + BAR_WIDTH / 2, 70],
  [336 + BAR_WIDTH / 2, 96],
];

const LINE_PATH = LINE_POINTS.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x},${y}`).join(" ");

export default function HeroVisual() {
  return (
    <svg
      viewBox="0 0 390 200"
      className="mx-auto w-full max-w-md"
      role="img"
      aria-label="Illustrative preview of a spend-by-category dashboard"
    >
      <style>{`
        .hero-bar {
          transform-origin: bottom;
          animation: hero-grow 0.7s cubic-bezier(0.22, 1, 0.36, 1) backwards;
        }
        .hero-line {
          stroke-dasharray: 520;
          stroke-dashoffset: 520;
          animation: hero-draw 1.1s 0.3s cubic-bezier(0.22, 1, 0.36, 1) forwards;
        }
        .hero-dot {
          opacity: 0;
          animation: hero-fade 0.4s 1.3s ease-out forwards;
        }
        .hero-pulse {
          animation: hero-pulse 2.4s ease-in-out infinite;
        }
        @keyframes hero-grow {
          from { transform: scaleY(0); }
          to { transform: scaleY(1); }
        }
        @keyframes hero-draw {
          to { stroke-dashoffset: 0; }
        }
        @keyframes hero-fade {
          to { opacity: 1; }
        }
        @keyframes hero-pulse {
          0%, 100% { opacity: 1; r: 4; }
          50% { opacity: 0.5; r: 6; }
        }
        @media (prefers-reduced-motion: reduce) {
          .hero-bar, .hero-line, .hero-dot, .hero-pulse { animation: none; opacity: 1; stroke-dashoffset: 0; }
        }
      `}</style>

      <rect x="0.5" y="0.5" width="389" height="199" rx="12" fill="var(--surface-1)" stroke="var(--border-hairline)" />

      {[40, 80, 120, 164].map((y) => (
        <line key={y} x1="16" y1={y} x2="374" y2={y} stroke="var(--gridline)" strokeWidth="1" />
      ))}

      {BARS.map((bar, i) => (
        <rect
          key={bar.x}
          className="hero-bar"
          x={bar.x}
          y={BASELINE - bar.height}
          width={BAR_WIDTH}
          height={bar.height}
          rx="4"
          fill={bar.color}
          fillOpacity="0.55"
          style={{ animationDelay: `${i * 0.06}s` }}
        />
      ))}

      <path d={LINE_PATH} className="hero-line" fill="none" stroke="var(--series-1)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

      {LINE_POINTS.map(([x, y], i) => (
        <circle
          key={x}
          className={i === LINE_POINTS.length - 1 ? "hero-dot hero-pulse" : "hero-dot"}
          cx={x}
          cy={y}
          r="4"
          fill="var(--surface-1)"
          stroke="var(--series-1)"
          strokeWidth="2"
          style={{ animationDelay: `${1.3 + i * 0.05}s` }}
        />
      ))}
    </svg>
  );
}
