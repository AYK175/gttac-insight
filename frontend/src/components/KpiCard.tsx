type Accent = "blue" | "amber" | "red" | "orange" | "purple";

const accentMap: Record<Accent, { bg: string; border: string; icon: string; text: string }> = {
  blue:   { bg: "bg-blue-50",   border: "border-blue-200",  icon: "bg-blue-500",   text: "text-blue-700" },
  amber:  { bg: "bg-amber-50",  border: "border-amber-200", icon: "bg-amber-500",  text: "text-amber-700" },
  red:    { bg: "bg-red-50",    border: "border-red-200",   icon: "bg-red-500",    text: "text-red-700" },
  orange: { bg: "bg-orange-50", border: "border-orange-200",icon: "bg-orange-500", text: "text-orange-700" },
  purple: { bg: "bg-purple-50", border: "border-purple-200",icon: "bg-purple-500", text: "text-purple-700" },
};

export function KpiCard(props: {
  label: string;
  value: string;
  sub?: string;
  accent?: Accent;
}) {
  const accent = props.accent ?? "blue";
  const a = accentMap[accent];

  return (
    <div className={`rounded-xl border ${a.border} ${a.bg} p-4 shadow-sm`}>
      <div className="flex items-start gap-3">
        <div className={`mt-0.5 h-2 w-2 rounded-full ${a.icon} shrink-0`} />
        <div className="min-w-0">
          <div className={`text-xs font-semibold uppercase tracking-wide ${a.text}`}>
            {props.label}
          </div>
          <div className="mt-1 text-2xl font-bold text-zinc-900">{props.value}</div>
          {props.sub ? (
            <div className="mt-1 truncate text-xs text-zinc-500">{props.sub}</div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
