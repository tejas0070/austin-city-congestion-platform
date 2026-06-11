import { useState } from 'react';
import EventCard from './EventCard';
import LayerToggle from './LayerToggle';
import TrafficLegend from './TrafficLegend';

export default function Sidebar({ events, weather, layers, onLayerToggle }) {
  const [activeTab, setActiveTab] = useState('layers');

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
              <LayerToggle
                key={key}
                label={key.replace(/_/g, ' ')}
                enabled={enabled}
                onToggle={() => onLayerToggle(key)}
              />
            ))}
            <div className="mt-4">
              <TrafficLegend />
            </div>
          </div>
        )}
        {activeTab === 'events' && (
          <div className="space-y-2">
            {events.length === 0 ? (
              <p className="text-xs text-gray-500">No upcoming events.</p>
            ) : (
              events.map((ev) => <EventCard key={ev.id ?? ev.name} event={ev} />)
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
