import { formatEventTime } from '../utils/datetime';

export default function EventCard({ event }) {
  const timeStr = formatEventTime(event.time);

  return (
    <div className="rounded-xl border border-stone bg-surface-hi p-3 transition-colors hover:border-violet/30">
      <p className="text-sm font-medium leading-snug text-ink">{event.name}</p>
      {timeStr && (
        <p className="mt-1 font-mono text-xs tabular-nums text-violet">{timeStr}</p>
      )}
      {event.venue && (
        <p className="mt-0.5 text-xs text-ink-soft">{event.venue}</p>
      )}
    </div>
  );
}
