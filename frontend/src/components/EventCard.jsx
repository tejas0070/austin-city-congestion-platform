import { format, parseISO } from 'date-fns';

export default function EventCard({ event }) {
  const dateStr = event.event_date
    ? format(parseISO(event.event_date), 'MMM d')
    : null;

  return (
    <div className="rounded-lg bg-gray-800 p-3">
      <p className="text-sm font-medium text-white leading-snug">{event.name}</p>
      {dateStr && (
        <p className="mt-1 text-xs text-gray-400">{dateStr}</p>
      )}
      {event.venue && (
        <p className="mt-0.5 text-xs text-gray-500">{event.venue}</p>
      )}
    </div>
  );
}
