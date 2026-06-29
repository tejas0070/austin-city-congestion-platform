const LEVEL_COLOR = {
  green: '#22C55E',
  yellow: '#FACC15',
  red: '#DC2626',
};

/**
 * 24-hour citywide congestion curve. Each bar's height encodes avg_pct and its
 * color encodes avg_level; the current hour is marked and bars are clickable.
 *
 * @param {{hours: Array, currentHour: number, onSelectHour: (h:number)=>void}} props
 */
export default function CongestionCurve({ hours, currentHour, onSelectHour }) {
  if (!hours?.length) {
    return <div className="h-12 rounded bg-stone-soft" />;
  }

  return (
    <div className="flex h-12 items-end gap-[2px]">
      {hours.map((h) => {
        const isCurrent = h.hour === currentHour;
        const heightPct = Math.max(6, Math.min(100, h.avg_pct));
        return (
          <button
            key={h.hour}
            type="button"
            onClick={() => onSelectHour(h.hour)}
            title={`${h.label} · ${Math.round(h.avg_pct)}% (${h.avg_level})`}
            aria-label={`${h.label}, ${h.avg_level} congestion`}
            className="group relative flex-1 self-stretch"
          >
            <span
              className="absolute bottom-0 left-0 right-0 rounded-sm transition-opacity"
              style={{
                height: `${heightPct}%`,
                backgroundColor: LEVEL_COLOR[h.avg_level] ?? LEVEL_COLOR.green,
                opacity: isCurrent ? 1 : 0.55,
              }}
            />
            {isCurrent && (
              <span className="absolute inset-y-0 left-1/2 w-[2px] -translate-x-1/2 bg-violet" />
            )}
          </button>
        );
      })}
    </div>
  );
}
