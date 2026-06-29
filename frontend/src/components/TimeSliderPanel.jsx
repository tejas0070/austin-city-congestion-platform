import { format, parseISO } from 'date-fns';
import CongestionCurve from './CongestionCurve';

const WEATHER_BADGE = {
  forecast: { label: 'Forecast', className: 'bg-signal-green/15 text-signal-green-ink' },
  mixed: { label: 'Forecast (part)', className: 'bg-signal-green/15 text-signal-green-ink' },
  proxy: { label: 'Est. weather', className: 'bg-signal-amber/20 text-signal-amber-ink' },
};

// Colour the confidence badge by its High/Medium/Low band.
const CONFIDENCE_BADGE = {
  High: 'bg-signal-green/15 text-signal-green-ink',
  Medium: 'bg-signal-amber/20 text-signal-amber-ink',
  Low: 'bg-signal-red/15 text-signal-red-ink',
};

function confidenceBadgeClass(label) {
  return CONFIDENCE_BADGE[label] || 'bg-stone-soft text-ink-soft';
}

function dayLabel(dateISO) {
  try {
    return format(parseISO(dateISO), 'EEE, MMM d');
  } catch {
    return dateISO;
  }
}

/**
 * Bottom overlay panel that drives day-preview mode: date, play/pause, hourly
 * slider, current-hour weather, and the 24-hour congestion curve.
 */
export default function TimeSliderPanel({
  dateISO,
  hours,
  currentHour,
  isPlaying,
  onTogglePlay,
  onSelectHour,
  onClose,
  weatherSource,
  confidenceAvg,
  confidenceLabel,
  loading,
  error,
}) {
  const hour = hours?.[currentHour];
  const badge = weatherSource ? WEATHER_BADGE[weatherSource] : null;
  const hasData = !loading && !error && hours.length > 0;
  const showDayConfidence = typeof confidenceAvg === 'number' && !!confidenceLabel;
  const hourHasConfidence = hour && typeof hour.confidence_avg === 'number';

  return (
    <div className="fixed bottom-4 left-[23.5rem] right-4 z-20 rounded-2xl border border-stone bg-surface/95 p-3 shadow-float backdrop-blur">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-baseline gap-2 truncate">
          <span className="font-display text-sm font-bold uppercase tracking-[0.1em] text-ink">{dayLabel(dateISO)}</span>
          {hour && <span className="font-mono text-xs tabular-nums text-ink-soft">{hour.label}</span>}
          {hour && (
            <span className="truncate font-mono text-xs tabular-nums text-ink-faint">
              · {Math.round(hour.temperature_f)}°F {hour.condition}
            </span>
          )}
          {hourHasConfidence && (
            <span className="truncate font-mono text-xs tabular-nums text-ink-faint">
              · {Math.round(hour.confidence_avg)}% confidence
            </span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {showDayConfidence && (
            <span
              title="Average forecast confidence across the whole day"
              className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${confidenceBadgeClass(confidenceLabel)}`}
            >
              Day {Math.round(confidenceAvg)}%
            </span>
          )}
          {badge && (
            <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${badge.className}`}>
              {badge.label}
            </span>
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label="Exit day preview"
            className="grid size-6 place-items-center rounded-md text-ink-soft transition-colors hover:bg-stone-soft hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-violet"
          >
            ✕
          </button>
        </div>
      </div>

      {error ? (
        <div className="flex h-12 items-center justify-center text-xs text-signal-red-ink">{error}</div>
      ) : loading ? (
        <div className="flex h-12 items-center justify-center font-mono text-xs uppercase tracking-wider text-ink-faint">Loading day…</div>
      ) : (
        <CongestionCurve hours={hours} currentHour={currentHour} onSelectHour={onSelectHour} />
      )}

      <div className="mt-2 flex items-center gap-3">
        <button
          type="button"
          onClick={onTogglePlay}
          disabled={!hasData}
          aria-label={isPlaying ? 'Pause' : 'Play'}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-violet text-sm text-white transition-colors hover:bg-violet-deep focus:outline-none focus-visible:ring-2 focus-visible:ring-violet focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-40"
        >
          {isPlaying ? '❚❚' : '▶'}
        </button>
        <input
          type="range"
          min="0"
          max="23"
          step="1"
          value={currentHour}
          onChange={(e) => onSelectHour(Number(e.target.value))}
          disabled={!hasData}
          aria-label="Hour of day"
          className="h-1 flex-1 cursor-pointer accent-violet disabled:opacity-40"
        />
        <span className="w-16 shrink-0 text-right font-mono text-xs tabular-nums text-ink-soft">{hour?.label ?? ''}</span>
      </div>
    </div>
  );
}
