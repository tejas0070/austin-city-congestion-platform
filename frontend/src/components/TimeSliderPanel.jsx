import { format, parseISO } from 'date-fns';
import CongestionCurve from './CongestionCurve';

const WEATHER_BADGE = {
  forecast: { label: 'Forecast', className: 'bg-emerald-500/20 text-emerald-300' },
  mixed: { label: 'Forecast (part)', className: 'bg-emerald-500/20 text-emerald-300' },
  proxy: { label: 'Est. weather', className: 'bg-amber-500/20 text-amber-300' },
};

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
  loading,
  error,
}) {
  const hour = hours?.[currentHour];
  const badge = weatherSource ? WEATHER_BADGE[weatherSource] : null;
  const hasData = !loading && !error && hours.length > 0;

  return (
    <div className="fixed bottom-4 left-[21rem] right-4 z-20 rounded-xl border border-gray-700 bg-gray-900/95 p-3 shadow-2xl backdrop-blur">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-baseline gap-2 truncate">
          <span className="text-sm font-semibold text-white">{dayLabel(dateISO)}</span>
          {hour && <span className="text-xs text-gray-300">{hour.label}</span>}
          {hour && (
            <span className="truncate text-xs text-gray-500">
              · {Math.round(hour.temperature_f)}°F {hour.condition}
            </span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {badge && (
            <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${badge.className}`}>
              {badge.label}
            </span>
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label="Exit day preview"
            className="text-gray-400 transition-colors hover:text-white"
          >
            ✕
          </button>
        </div>
      </div>

      {error ? (
        <div className="flex h-12 items-center justify-center text-xs text-red-400">{error}</div>
      ) : loading ? (
        <div className="flex h-12 items-center justify-center text-xs text-gray-400">Loading day…</div>
      ) : (
        <CongestionCurve hours={hours} currentHour={currentHour} onSelectHour={onSelectHour} />
      )}

      <div className="mt-2 flex items-center gap-3">
        <button
          type="button"
          onClick={onTogglePlay}
          disabled={!hasData}
          aria-label={isPlaying ? 'Pause' : 'Play'}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm text-white transition-colors hover:bg-blue-500 disabled:opacity-40"
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
          className="h-1 flex-1 cursor-pointer accent-blue-500 disabled:opacity-40"
        />
        <span className="w-16 shrink-0 text-right text-xs text-gray-300">{hour?.label ?? ''}</span>
      </div>
    </div>
  );
}
