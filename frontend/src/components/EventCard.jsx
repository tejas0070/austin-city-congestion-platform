import { formatEventTime } from '../utils/datetime';

export default function EventCard({ event }) {
  const timeStr = formatEventTime(event.time);

  return (
    <div className="rounded-lg bg-gray-800 p-3">
      <p className="text-sm font-medium text-white leading-snug">{event.name}</p>
      {timeStr && (
        <p className="mt-1 text-xs font-medium text-blue-300">{timeStr}</p>
      )}
      {event.venue && (
        <p className="mt-0.5 text-xs text-gray-500">{event.venue}</p>
      )}
    </div>
  );
}
