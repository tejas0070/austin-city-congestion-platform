import { format, parseISO } from 'date-fns';
import MetricReadout from './MetricReadout';
import {
  CONFIDENCE_COLOR,
  congestionColor,
  congestionWord,
  weekdayInitial,
  barHeightPct,
} from '../../utils/modelMetrics';
import {
  CONFIDENCE_PILL,
  CONGESTION_PILL,
  CONFIDENCE_ACCENT,
  CONGESTION_ACCENT,
} from './cardPills';

function short(dateISO) {
  try {
    return format(parseISO(dateISO), 'MMM d');
  } catch {
    return dateISO;
  }
}

function round(value) {
  return typeof value === 'number' ? Math.round(value) : null;
}

const CARD = 'rounded-xl border border-stone bg-surface-hi p-3.5';

/**
 * Week-scale model card: a Confidence readout and a Congestion readout, each a
 * 7-day Mon–Sun trend so the user can compare how reliable and how heavy each
 * day is. Day bars are clickable to preview that day; the selected day is
 * highlighted in both rows.
 *
 * @param {{
 *   week: {
 *     days: Array, confidenceAvg: number|null, confidenceLabel: string|null,
 *     congestionAvg: number|null, congestionLevel: string|null,
 *     startDate: string, endDate: string|null,
 *     loading?: boolean, error?: string|null, unavailable?: boolean,
 *   },
 *   selectedISO: string,
 *   onSelectDay: (iso: string) => void,
 * }} props
 */
export default function WeekModelCard({ week, selectedISO, onSelectDay }) {
  const {
    days = [],
    confidenceAvg,
    confidenceLabel,
    congestionAvg,
    congestionLevel,
    startDate,
    endDate,
    loading,
    error,
    unavailable,
  } = week;

  const header = (
    <div className="mb-3 font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-ink-faint">
      Week · {short(startDate)}
      {endDate ? ` – ${short(endDate)}` : ''} · Mon–Sun
    </div>
  );

  if (unavailable) {
    return (
      <div className={CARD}>
        {header}
        <p className="text-[11px] text-ink-faint">Week forecast unavailable for this date range.</p>
      </div>
    );
  }
  if (error) {
    return (
      <div className={CARD}>
        {header}
        <p className="text-[11px] text-signal-red-ink">{error}</p>
      </div>
    );
  }
  if (loading && days.length === 0) {
    return (
      <div className={CARD}>
        {header}
        <div className="h-32 animate-pulse rounded bg-stone-soft" />
      </div>
    );
  }

  const handleSelect = (i) => {
    const iso = days[i]?.date;
    if (iso) onSelectDay(iso);
  };

  const confBars = days.map((d) => ({
    heightPct: barHeightPct(d.confidence_avg),
    color: CONFIDENCE_COLOR,
    topLabel: round(d.confidence_avg) ?? '—',
    bottomLabel: weekdayInitial(d.weekday),
    selected: d.date === selectedISO,
    title: `${d.weekday}: ${round(d.confidence_avg) ?? '—'}% confidence`,
  }));
  const congBars = days.map((d) => ({
    heightPct: barHeightPct(d.congestion_avg),
    color: congestionColor(d.congestion_level),
    topLabel: round(d.congestion_avg) ?? '—',
    bottomLabel: weekdayInitial(d.weekday),
    selected: d.date === selectedISO,
    title: `${d.weekday}: ${round(d.congestion_avg) ?? '—'}% congestion`,
  }));

  return (
    <div className={CARD}>
      {header}

      <MetricReadout
        marker="◆"
        markerColor={CONFIDENCE_ACCENT}
        title={`Confidence · avg ${typeof confidenceAvg === 'number' ? `${round(confidenceAvg)}%` : '—'}`}
        value={typeof confidenceAvg === 'number' ? `${round(confidenceAvg)}%` : '—'}
        pillText={confidenceLabel ?? undefined}
        pillClass={CONFIDENCE_PILL[confidenceLabel] ?? ''}
        bars={confBars}
        areaHeight={56}
        gap={6}
        onSelect={handleSelect}
      />

      <div className="my-3.5 h-px bg-stone" />

      <MetricReadout
        marker="▮"
        markerColor={CONGESTION_ACCENT}
        title={`Congestion · avg ${congestionLevel ? congestionWord(congestionLevel) : '—'}`}
        value={typeof congestionAvg === 'number' ? `${round(congestionAvg)}%` : '—'}
        pillText={congestionLevel ? congestionWord(congestionLevel) : undefined}
        pillClass={CONGESTION_PILL[congestionLevel] ?? ''}
        bars={congBars}
        areaHeight={56}
        gap={6}
        onSelect={handleSelect}
      />
    </div>
  );
}
