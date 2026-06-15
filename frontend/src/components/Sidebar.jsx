import { useMemo, useState } from 'react';
import EventCard from './EventCard';
import LayerToggle from './LayerToggle';
import TrafficLegend from './TrafficLegend';
import { formatClock, formatDayClock, formatEventDay } from '../utils/datetime';

/**
 * Group a date-sorted event list into ordered day buckets for an agenda view.
 * @param {Array<{date?: string}>} events
 * @returns {Array<{date: string, label: string, items: Array}>}
 */
function groupEventsByDay(events) {
  const groups = [];
  const indexByDate = new Map();
  for (const ev of events) {
    const date = ev.date ?? 'unknown';
    if (!indexByDate.has(date)) {
      indexByDate.set(date, groups.length);
      groups.push({ date, label: formatEventDay(date), items: [] });
    }
    groups[indexByDate.get(date)].items.push(ev);
  }
  return groups;
}

export default function Sidebar({
  events,
  weather,
  layers,
  onLayerToggle,
  liveUpdatedAt,
  predictedFor,
  onOpenCalendar,
}) {
  const [activeTab, setActiveTab] = useState('layers');

  const eventGroups = useMemo(() => groupEventsByDay(events), [events]);

  // Small "as of / for" caption shown beneath the relevant layer toggle.
  const liveCaption = formatClock(liveUpdatedAt);
  const predictedCaption = formatDayClock(predictedFor);
  const layerCaptions = {
    live_traffic: liveCaption && `Live · as of ${liveCaption}`,
    predicted: predictedCaption && `Predicted · for ${predictedCaption}`,
  };

  return (
    <aside className="flex h-full w-80 flex-col bg-gray-900 border-r border-gray-800">
      {/* Header */}
      <div className="border-b border-gray-800 px-4 py-3">
        <h1 className="text-sm font-bold uppercase tracking-widest text-white">
          Austin Traffic
        </h1>
        {weather && (
          <p className="mt-0.5 text-xs text-gray-400">
            {weather.temperature_f}°F · {weather.condition}
            {weather.rain_alert && (
              <span className="ml-1 text-yellow-400">⚠ Rain</span>
            )}
          </p>
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-800">
        {['layers', 'events'].map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`flex-1 py-2 text-xs font-semibold uppercase tracking-wide transition-colors ${
              activeTab === tab
                ? 'border-b-2 border-blue-500 text-blue-400'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3">
        {activeTab === 'layers' && (
          <div className="space-y-2">
            {Object.entries(layers).map(([key, enabled]) => (
              <div key={key}>
                <LayerToggle
                  label={key.replace(/_/g, ' ')}
                  enabled={enabled}
                  onToggle={() => onLayerToggle(key)}
                />
                {layerCaptions[key] && (
                  <p className="mt-0.5 px-1 text-[10px] text-gray-500">
                    {layerCaptions[key]}
                  </p>
                )}
              </div>
            ))}
            <div className="mt-4">
              <TrafficLegend />
            </div>
          </div>
        )}
        {activeTab === 'events' && (
          <div className="space-y-4">
            <button
              type="button"
              onClick={onOpenCalendar}
              className="flex w-full items-center justify-center gap-2 rounded-md bg-blue-600 py-2 text-xs font-semibold uppercase tracking-wide text-white transition-colors hover:bg-blue-500"
            >
              <span>🗓</span> Open calendar
            </button>
            {eventGroups.length === 0 ? (
              <p className="text-xs text-gray-500">No upcoming events.</p>
            ) : (
              eventGroups.map((group) => (
                <div key={group.date} className="space-y-2">
                  <p className="sticky top-0 -mx-1 bg-gray-900/95 px-1 py-1 text-xs font-semibold uppercase tracking-wide text-blue-400">
                    {group.label}
                  </p>
                  {group.items.map((ev) => (
                    <EventCard key={ev.id ?? ev.name} event={ev} />
                  ))}
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
