// Swatches mirror the map's congestion ramp exactly, drawn as short line
// segments to echo how the data appears on the map (roads, not dots).
const LEGEND_ITEMS = [
  { color: 'bg-signal-green', label: 'Free flow' },
  { color: 'bg-signal-amber', label: 'Moderate' },
  { color: 'bg-signal-red', label: 'Heavy' },
];

const CONFIDENCE_DOT = {
  High: 'bg-signal-green',
  Medium: 'bg-signal-amber',
  Low: 'bg-signal-red',
};

export default function TrafficLegend({ confidenceAvg, confidenceLabel, confidenceScope }) {
  const showConfidence = typeof confidenceAvg === 'number' && !!confidenceLabel;
  const confidenceHeading = confidenceScope || 'Forecast confidence';
  return (
    <div className="rounded-xl border border-stone bg-surface-hi p-3">
      <p className="mb-2 font-display text-[10px] font-bold uppercase tracking-[0.16em] text-ink-soft">
        Traffic
      </p>
      <ul className="space-y-1.5">
        {LEGEND_ITEMS.map(({ color, label }) => (
          <li key={label} className="flex items-center gap-2.5">
            <span className={`h-1.5 w-5 rounded-full ${color}`} />
            <span className="text-xs text-ink">{label}</span>
          </li>
        ))}
      </ul>
      {showConfidence && (
        <div className="mt-3 border-t border-stone pt-2">
          <p className="font-display text-[10px] font-bold uppercase tracking-[0.16em] text-ink-soft">
            {confidenceHeading}
          </p>
          <div className="mt-1.5 flex items-center gap-2.5">
            <span className={`h-3 w-3 rounded-full ${CONFIDENCE_DOT[confidenceLabel] ?? 'bg-stone'}`} />
            <span className="font-mono text-xs tabular-nums text-ink">
              {confidenceAvg}% ({confidenceLabel})
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
