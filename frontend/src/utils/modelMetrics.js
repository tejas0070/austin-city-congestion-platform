import { startOfWeek, addDays, format, parseISO } from 'date-fns';

/**
 * Monday-first week containing an ISO date ("YYYY-MM-DD").
 * Returns the Monday's ISO plus the 7 day ISO strings Mon..Sun.
 *
 * @param {string} dateISO
 * @returns {{ mondayISO: string, days: string[] }}
 */
export function weekBounds(dateISO) {
  const base = parseISO(dateISO);
  const monday = startOfWeek(base, { weekStartsOn: 1 });
  const days = [];
  for (let i = 0; i < 7; i += 1) {
    days.push(format(addDays(monday, i), 'yyyy-MM-dd'));
  }
  return { mondayISO: days[0], days };
}

// Confidence is drawn in BLUE so it never competes with the green/yellow/red
// traffic ramp. A single hue keeps "this is the confidence metric" unambiguous.
export const CONFIDENCE_COLOR = '#6B5B95';

// Congestion level -> hex, matching the map's congestion ramp.
const CONGESTION_LEVEL_COLOR = {
  green: '#22C55E',
  yellow: '#FACC15',
  red: '#DC2626',
};

/** Hex color for a congestion level ('green' | 'yellow' | 'red'). */
export function congestionColor(level) {
  return CONGESTION_LEVEL_COLOR[level] ?? CONGESTION_LEVEL_COLOR.green;
}

// Confidence High/Medium/Low thresholds — mirror backend etl/confidence.py.
const HIGH_THRESHOLD = 75;
const MEDIUM_THRESHOLD = 50;

/** Confidence band label for a 0-100 score. */
export function confidenceBand(pct) {
  if (pct >= HIGH_THRESHOLD) return 'High';
  if (pct >= MEDIUM_THRESHOLD) return 'Medium';
  return 'Low';
}

// Plain-English congestion word for a level, for the readout pill.
const CONGESTION_WORD = { green: 'Light', yellow: 'Moderate', red: 'Heavy' };

/** Plain-English congestion word for a level. */
export function congestionWord(level) {
  return CONGESTION_WORD[level] ?? 'Unknown';
}

/** First letter of a weekday name ("Monday" -> "M"). */
export function weekdayInitial(weekday) {
  return weekday ? weekday[0] : '';
}

/**
 * Bar height as a clamped percentage with a small floor so a near-zero value is
 * still visible. Pure helper shared by the day and week graphs.
 *
 * @param {number} value 0-100
 * @param {number} floor minimum height percent
 * @returns {number}
 */
export function barHeightPct(value, floor = 6) {
  if (typeof value !== 'number' || Number.isNaN(value)) return floor;
  return Math.max(floor, Math.min(100, value));
}
