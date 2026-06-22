import { format, parseISO } from 'date-fns';
import MetricReadout from './MetricReadout';
import {
  CONFIDENCE_COLOR,
  congestionColor,
  congestionWord,
  barHeightPct,
} from '../../utils/modelMetrics';
import {
  CONFIDENCE_PILL,
  CONGESTION_PILL,
  CONFIDENCE_ACCENT,
  CONGESTION_ACCENT,
} from './cardPills';

const HOUR_AXIS = ['12a', '6a', '12p', '6p', '11p'];

function dayLabel(dateISO) {
  try {
    return format(parseISO(dateISO), 'EEE, MMM d');
  } catch {
    return dateISO;
  }
}

function round(value) {
  return typeof value === 'number' ? Math.round(value) : null;
}

/** Sub-note describing the lowest-confidence hour, e.g. "low 30% · 7:00 AM". */
function confidenceRange(hours) {
  const withConf = hours.filter((h) => typeof h.confidence_avg === 'number');
  if (withConf.length === 0) return null;
  const lowest = withConf.reduce((a, b) => (b.confidence_avg < a.confidence_avg ? b : a));
  return `low ${Math.round(lowest.confidence_avg)}% · ${lowest.label}`;
}

/** Sub-note describing the peak-congestion hour, e.g. "peak 81% · 5:00 PM". */
function congestionPeak(hours) {
  if (hours.length === 0) return null;
  const peak = hours.reduce((a, b) => (b.avg_pct > a.avg_pct ? b : a));
  return `peak ${Math.round(peak.avg_pct)}% · ${peak.label}`;
}

/**
 * Day-scale model card: a Confidence readout and a Congestion readout, each a
 * number plus a 24-hour trend graph, so the user can see how each metric moves
 * across the day (e.g. confidence dipping when congestion peaks).
 *
 * @param {{ day: {
 *   date: string, confidenceAvg: number|null, confidenceLabel: string|null,
 *   congestionAvg: number|null, congestionLevel: string|null, hours: Array,
 *   loading?: boolean,
 * } }} props
 */
export default function DayModelCard({ day }) {
  const { date, confidenceAvg, confidenceLabel, congestionAvg, congestionLevel, hours = [], loading } =
    day;

  if (loading && hours.length === 0) {
    return (
      <div className="rounded-xl border border-gray-700 bg-gray-900 p-3.5">
        <div className="mb-3 text-[10px] font-semibold uppercase tracking-wide text-gray-500">
          Day · {dayLabel(date)}
        </div>
        <div className="h-28 animate-pulse rounded bg-gray-800" />
      </div>
    );
  }

  const confBars = hours.map((h) => ({
    heightPct: barHeightPct(h.confidence_avg),
    color: CONFIDENCE_COLOR,
    title: `${h.label}: ${round(h.confidence_avg) ?? '—'}% confidence`,
  }));
  const congBars = hours.map((h) => ({
    heightPct: barHeightPct(h.avg_pct),
    color: congestionColor(h.avg_level),
    title: `${h.label}: ${round(h.avg_pct)}% congestion`,
  }));

  const hasConfidence = typeof confidenceAvg === 'number';

  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 p-3.5">
      <div className="mb-3 text-[10px] font-semibold uppercase tracking-wide text-gray-500">
        Day · {dayLabel(date)}
      </div>

      <MetricReadout
        marker="◆"
        markerColor={CONFIDENCE_ACCENT}
        title="Confidence"
        value={hasConfidence ? `${round(confidenceAvg)}%` : '—'}
        pillText={hasConfidence ? confidenceLabel : undefined}
        pillClass={CONFIDENCE_PILL[confidenceLabel] ?? ''}
        subNote={confidenceRange(hours)}
        bars={hasConfidence ? confBars : undefined}
        areaHeight={40}
        gap={1}
        axis={HOUR_AXIS}
        emptyNote="Confidence unavailable for this forecast."
      />

      <div className="my-3.5 h-px bg-gray-700" />

      <MetricReadout
        marker="▮"
        markerColor={CONGESTION_ACCENT}
        title="Congestion"
        value={typeof congestionAvg === 'number' ? `${round(congestionAvg)}%` : '—'}
        pillText={congestionLevel ? congestionWord(congestionLevel) : undefined}
        pillClass={CONGESTION_PILL[congestionLevel] ?? ''}
        subNote={congestionPeak(hours)}
        bars={congBars}
        areaHeight={40}
        gap={1}
        axis={HOUR_AXIS}
      />
    </div>
  );
}
