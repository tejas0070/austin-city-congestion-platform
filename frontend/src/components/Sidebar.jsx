import { useMemo, useState } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import { Layers, Ticket, Activity, X, AlertTriangle } from 'lucide-react';
import EventCard from './EventCard';
import LayerToggle from './LayerToggle';
import TrafficLegend from './TrafficLegend';
import ModelPanel from './model/ModelPanel';
import SidebarMenu from './sidebar/SidebarMenu';
import { formatClock, formatDayClock, formatEventDay } from '../utils/datetime';

const EASE = [0.16, 1, 0.3, 1];

// The three openable sections. Calendar is handled separately (it opens a modal,
// not a panel). Order: what you act on (layers) → the forecast → events.
const SECTIONS = [
  { key: 'layers', label: 'Map Layers', icon: Layers, hint: 'Live · Predicted' },
  { key: 'forecast', label: 'Forecast Model', icon: Activity, hint: 'Confidence' },
  { key: 'events', label: 'Events', icon: Ticket, hint: 'Upcoming' },
];

/**
 * Turn a snake_case layer key into a Title Case label (live_traffic → Live Traffic).
 * @param {string} key
 * @returns {string}
 */
function titleizeLayer(key) {
  return key
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

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
  modelAccuracyPct,
  modelAccuracyLoading,
  dayCard,
  week,
  selectedISO,
  onSelectDay,
}) {
  // Two-step disclosure: a collapsed console (menuOpen toggles its list), and a
  // floating panel for the chosen section. Opening a section collapses the list;
  // closing the panel (X) returns to the open list so another section is a tap away.
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeSection, setActiveSection] = useState(null);
  const reduce = useReducedMotion();

  const eventGroups = useMemo(() => groupEventsByDay(events), [events]);

  const liveCaption = formatClock(liveUpdatedAt);
  const predictedCaption = formatDayClock(predictedFor);
  const layerCaptions = {
    live_traffic: liveCaption && `Live · as of ${liveCaption}`,
    predicted: predictedCaption && `Predicted · for ${predictedCaption}`,
  };

  const section = SECTIONS.find((s) => s.key === activeSection);

  function openSection(key) {
    setActiveSection(key);
    setMenuOpen(false);
  }

  function closePanel() {
    setActiveSection(null);
    setMenuOpen(true);
  }

  function handleOpenCalendar() {
    setMenuOpen(false);
    onOpenCalendar();
  }

  return (
    <div className="pointer-events-none absolute inset-y-4 left-4 z-40 flex">
      <AnimatePresence mode="wait" initial={false}>
        {section ? (
          <motion.aside
            key="panel"
            initial={reduce ? { opacity: 0 } : { opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, x: -12 }}
            transition={{ duration: 0.22, ease: EASE }}
            className="pointer-events-auto flex max-h-full w-[344px] flex-col overflow-hidden rounded-2xl border border-stone bg-surface/95 shadow-float backdrop-blur"
            aria-label={section.label}
          >
            {/* Panel header with the violet-crown hairline signature. */}
            <header className="relative flex shrink-0 items-center gap-2.5 px-4 py-3">
              <span className="grid size-7 place-items-center rounded-lg bg-violet-tint text-violet">
                <section.icon className="size-[16px]" />
              </span>
              <h2 className="font-display text-[13px] font-bold uppercase tracking-[0.16em] text-ink">
                {section.label}
              </h2>
              {weather && (
                <span className="ml-auto flex items-center gap-1 font-mono text-xs tabular-nums text-ink-soft">
                  {Math.round(weather.temperature_f)}°F
                  {weather.rain_alert && (
                    <AlertTriangle className="size-3.5 text-signal-amber-ink" aria-label="Rain alert" />
                  )}
                </span>
              )}
              <button
                type="button"
                onClick={closePanel}
                aria-label="Close panel"
                className={`grid size-7 place-items-center rounded-lg text-ink-soft transition-colors hover:bg-stone-soft hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-violet ${weather ? 'ml-2' : 'ml-auto'}`}
              >
                <X className="size-4" />
              </button>
              <span className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-violet/0 via-violet to-violet/0" />
            </header>

            <div className="flex-1 overflow-y-auto px-3 pb-3 pt-3">
              {activeSection === 'layers' && (
                <div className="space-y-2">
                  {Object.entries(layers).map(([key, enabled]) => (
                    <div key={key}>
                      <LayerToggle
                        label={titleizeLayer(key)}
                        enabled={enabled}
                        onToggle={() => onLayerToggle(key)}
                      />
                      {layerCaptions[key] && (
                        <p className="mt-1 px-3 font-mono text-[10px] uppercase tracking-wider text-ink-faint">
                          {layerCaptions[key]}
                        </p>
                      )}
                    </div>
                  ))}
                  <div className="pt-2">
                    <TrafficLegend />
                  </div>
                </div>
              )}

              {activeSection === 'forecast' && (
                <ModelPanel
                  accuracyPct={modelAccuracyPct}
                  accuracyLoading={modelAccuracyLoading}
                  day={dayCard}
                  week={week}
                  selectedISO={selectedISO}
                  onSelectDay={onSelectDay}
                />
              )}

              {activeSection === 'events' && (
                <div className="space-y-4">
                  {eventGroups.length === 0 ? (
                    <p className="px-1 py-6 text-center text-sm text-ink-soft">No upcoming events.</p>
                  ) : (
                    eventGroups.map((group) => (
                      <div key={group.date} className="space-y-2">
                        <p className="sticky top-0 -mx-1 bg-surface/95 px-1 py-1 font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-violet backdrop-blur">
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
          </motion.aside>
        ) : (
          <motion.div
            key="menu"
            initial={reduce ? { opacity: 0 } : { opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, x: -12 }}
            transition={{ duration: 0.22, ease: EASE }}
            className="pointer-events-auto self-start"
          >
            <SidebarMenu
              sections={SECTIONS}
              open={menuOpen}
              onToggle={() => setMenuOpen((v) => !v)}
              onSelect={openSection}
              onOpenCalendar={handleOpenCalendar}
              weather={weather}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
