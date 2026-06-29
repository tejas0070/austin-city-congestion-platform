import { useState } from 'react';
import { format } from 'date-fns';
import {
  buildMonthGrid,
  eventsByDay,
  toISODate,
  isWithinRange,
  categoryColor,
} from '../utils/calendar';

const WEEKDAYS = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
const MAX_CHIPS = 2;

/**
 * Month-grid calendar overlay. Event chips sit in day cells; clicking a
 * selectable day (in-month and within [minISO, maxISO]) calls onSelectDay(iso).
 */
export default function EventCalendar({ events, onSelectDay, onClose, minISO, maxISO, initialDate }) {
  const base = initialDate ?? new Date();
  const [view, setView] = useState({ year: base.getFullYear(), month: base.getMonth() });

  const weeks = buildMonthGrid(view.year, view.month);
  const byDay = eventsByDay(events);
  const todayISO = toISODate(new Date());
  const monthLabel = format(new Date(view.year, view.month, 1), 'MMMM yyyy');

  function shiftMonth(delta) {
    setView((v) => {
      const d = new Date(v.year, v.month + delta, 1);
      return { year: d.getFullYear(), month: d.getMonth() };
    });
  }

  return (
    <div
      className="fixed inset-0 z-30 flex items-center justify-center bg-black/60 p-6"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="w-full max-w-2xl rounded-2xl border border-stone bg-surface p-4 shadow-float"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-display text-base font-bold uppercase tracking-[0.12em] text-ink">{monthLabel}</h2>
          <div className="flex items-center gap-1 text-ink-soft">
            <button type="button" onClick={() => shiftMonth(-1)} aria-label="Previous month" className="grid size-7 place-items-center rounded-md transition-colors hover:bg-stone-soft hover:text-ink">◀</button>
            <button type="button" onClick={() => shiftMonth(1)} aria-label="Next month" className="grid size-7 place-items-center rounded-md transition-colors hover:bg-stone-soft hover:text-ink">▶</button>
            <button type="button" onClick={onClose} aria-label="Close calendar" className="ml-1 grid size-7 place-items-center rounded-md transition-colors hover:bg-stone-soft hover:text-ink">✕</button>
          </div>
        </div>

        <div className="mb-1 grid grid-cols-7 gap-1">
          {WEEKDAYS.map((d) => (
            <div key={d} className="text-center font-mono text-[10px] font-semibold tracking-[0.1em] text-ink-faint">{d}</div>
          ))}
        </div>

        <div className="grid grid-cols-7 gap-1">
          {weeks.flat().map((cell) => {
            const dayEvents = byDay.get(cell.iso) ?? [];
            const selectable = cell.inMonth && isWithinRange(cell.iso, minISO, maxISO);
            const isToday = cell.iso === todayISO;
            return (
              <button
                key={cell.iso}
                type="button"
                disabled={!selectable}
                onClick={() => selectable && onSelectDay(cell.iso)}
                className={[
                  'flex h-16 flex-col rounded-lg border p-1 text-left transition-colors',
                  cell.inMonth ? 'border-stone bg-surface-hi' : 'border-transparent bg-stone-soft/40',
                  selectable ? 'cursor-pointer hover:border-violet/40 hover:bg-violet-tint' : 'cursor-default',
                  isToday ? 'ring-2 ring-violet' : '',
                ].join(' ')}
              >
                <span className={`font-mono text-[10px] tabular-nums ${cell.inMonth ? 'text-ink' : 'text-ink-faint'} ${!selectable && cell.inMonth ? 'opacity-50' : ''}`}>
                  {cell.day}
                </span>
                <div className="mt-0.5 flex flex-col gap-0.5 overflow-hidden">
                  {dayEvents.slice(0, MAX_CHIPS).map((ev) => (
                    <span
                      key={ev.id ?? ev.name}
                      title={ev.name}
                      className="truncate rounded-sm px-1 text-[8px] font-medium leading-tight text-white"
                      style={{ backgroundColor: categoryColor(ev.category) }}
                    >
                      {ev.name}
                    </span>
                  ))}
                  {dayEvents.length > MAX_CHIPS && (
                    <span className="text-[8px] text-ink-soft">+{dayEvents.length - MAX_CHIPS} more</span>
                  )}
                </div>
              </button>
            );
          })}
        </div>

        <div className="mt-3 flex items-center gap-4 text-[10px] text-ink-soft">
          <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-sm" style={{ background: '#3B82F6' }} /> Sports</span>
          <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-sm" style={{ background: '#A855F7' }} /> Music</span>
          <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-sm" style={{ background: '#22C55E' }} /> Other</span>
          <span className="ml-auto font-mono uppercase tracking-wide text-violet">Click a day to preview traffic by hour</span>
        </div>
      </div>
    </div>
  );
}
