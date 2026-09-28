export function ProgressRing({ value, size = 88, label }: { value: number; size?: number; label?: string }) {
  const clamped = Math.max(0, Math.min(100, value));
  const stroke = 8;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (clamped / 100) * circumference;

  return (
    <div
      role="img"
      aria-label={label || `التقدم ${clamped}%`}
      className="relative inline-flex items-center justify-center motion-safe:[&_circle.value]:transition-[stroke-dashoffset] motion-safe:[&_circle.value]:duration-700"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} strokeWidth={stroke} className="fill-none stroke-[var(--border)]" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={stroke}
          strokeLinecap="round"
          className="value fill-none stroke-[var(--primary)]"
          style={{ strokeDasharray: circumference, strokeDashoffset: offset }}
        />
      </svg>
      <span className="text-metric absolute text-h3">{clamped}%</span>
    </div>
  );
}
