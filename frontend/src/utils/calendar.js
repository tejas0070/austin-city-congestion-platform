import {
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  eachDayOfInterval,
  isSameMonth,
  format,
} from 'date-fns';

/**
 * Local-time ISO date string ("YYYY-MM-DD") for a Date.
 * @param {Date} date
 * @returns {string}
 */
export function toISODate(date) {
  return format(date, 'yyyy-MM-dd');
}

/**
 * Build a Sunday-aligned month grid: an array of weeks, each a 7-cell array.
 * Cells from adjacent months are included (to fill weeks) and flagged inMonth=false.
 * @param {number} year   full year, e.g. 2026
 * @param {number} month  0-indexed month (0 = January)
 * @returns {Array<Array<{date: Date, iso: string, day: number, inMonth: boolean}>>}
 */
export function buildMonthGrid(year, month) {
  const first = new Date(year, month, 1);
  const gridStart = startOfWeek(startOfMonth(first), { weekStartsOn: 0 });
  const gridEnd = endOfWeek(endOfMonth(first), { weekStartsOn: 0 });
  const days = eachDayOfInterval({ start: gridStart, end: gridEnd });

  const cells = days.map((d) => ({
    date: d,
    iso: toISODate(d),
    day: d.getDate(),
    inMonth: isSameMonth(d, first),
  }));

  const weeks = [];
  for (let i = 0; i < cells.length; i += 7) {
    weeks.push(cells.slice(i, i + 7));
  }
  return weeks;
}

/**
 * Index events by their date string ("YYYY-MM-DD").
 * @param {Array<{date?: string}>} events
 * @returns {Map<string, Array>}
 */
export function eventsByDay(events) {
  const map = new Map();
  for (const ev of events || []) {
    if (!ev?.date) continue;
    if (!map.has(ev.date)) map.set(ev.date, []);
    map.get(ev.date).push(ev);
  }
  return map;
}

/**
 * Whether an ISO date string falls within [minISO, maxISO] inclusive.
 * Lexicographic comparison is valid for zero-padded ISO dates.
 * @param {string} iso
 * @param {string} minISO
 * @param {string} maxISO
 * @returns {boolean}
 */
export function isWithinRange(iso, minISO, maxISO) {
  return iso >= minISO && iso <= maxISO;
}

/** Map an event category to its chip color hex (matches the map's event colors). */
export function categoryColor(category) {
  if (category === 'Sports') return '#3B82F6';
  if (category === 'Music') return '#A855F7';
  return '#22C55E';
}
