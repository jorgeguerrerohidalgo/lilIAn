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

export function RiskScoreBar({ score, level }: RiskScoreBarProps) {
  const width = Math.min(100, Math.max(0, score));
  const colorClass = RISK_LEVEL_COLORS[level] || "bg-slate-400";

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-soft rounded-full overflow-hidden">
        <div
          className={`h-full ${colorClass} transition-all duration-500`}
          style={{ width: `${width}%` }}
        />
      </div>
      <span className="text-sm font-medium text-ink min-w-[3rem] text-right">
        {score}/100
      </span>
    </div>
  );
}
