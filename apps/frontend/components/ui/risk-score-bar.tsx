interface RiskScoreBarProps {
  score: number;
  level: string;
}

const RISK_LEVEL_COLORS: Record<string, string> = {
  low: "bg-green",
  medium: "bg-amber",
  high: "bg-coral",
  critical: "bg-coral-dark",
};

// S5 accessibility: human-readable labels for each risk level so screen
// readers can announce the severity in addition to the color and score.
const RISK_LEVEL_LABELS: Record<string, string> = {
  low: "Bajo",
  medium: "Medio",
  high: "Alto",
  critical: "Crítico",
};

export function RiskScoreBar({ score, level }: RiskScoreBarProps) {
  const width = Math.min(100, Math.max(0, score));
  const colorClass = RISK_LEVEL_COLORS[level] || "bg-slate-400";
  const levelLabel = RISK_LEVEL_LABELS[level] || "Sin clasificar";

  return (
    <div
      className="flex items-center gap-2"
      role="meter"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={score}
      aria-valuetext={`Nivel de riesgo ${levelLabel}: ${score} de 100`}
    >
      <div className="flex-1 h-2 bg-soft rounded-full overflow-hidden" aria-hidden="true">
        <div
          className={`h-full ${colorClass} transition-all duration-500`}
          style={{ width: `${width}%` }}
        />
      </div>
      <span className="text-sm font-medium text-ink min-w-[3rem] text-right">
        {score}/100
        <span className="sr-only">. Nivel de riesgo: {levelLabel}</span>
      </span>
    </div>
  );
}
