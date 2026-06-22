import ModelAccuracyBadge from './ModelAccuracyBadge';
import DayModelCard from './DayModelCard';
import WeekModelCard from './WeekModelCard';

/**
 * Always-on sidebar panel that surfaces the forecast model's accuracy plus
 * day-scale and week-scale Confidence and Congestion readouts. Stacks under the
 * traffic legend.
 *
 * @param {{
 *   accuracyPct: number | null,
 *   accuracyLoading?: boolean,
 *   day: object,
 *   week: object,
 *   selectedISO: string,
 *   onSelectDay: (iso: string) => void,
 * }} props
 */
export default function ModelPanel({
  accuracyPct,
  accuracyLoading,
  day,
  week,
  selectedISO,
  onSelectDay,
}) {
  return (
    <div className="flex flex-col gap-3">
      <ModelAccuracyBadge accuracyPct={accuracyPct} loading={accuracyLoading} />
      <DayModelCard day={day} />
      <WeekModelCard week={week} selectedISO={selectedISO} onSelectDay={onSelectDay} />
    </div>
  );
}
