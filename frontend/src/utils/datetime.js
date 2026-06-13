import { format, parseISO } from 'date-fns';

/**
 * Format an ISO timestamp (naive local, e.g. "2026-06-13T15:45:00") as a clock
 * time like "3:45 PM". Returns null on missing/invalid input.
 * @param {string | null | undefined} iso
 * @returns {string | null}
 */
export function formatClock(iso) {
  if (!iso) return null;
  try {
    return format(parseISO(iso), 'h:mm a');
  } catch {
    return null;
  }
}

/**
 * Format an ISO timestamp as "MMM d · h:mm a" — used for future times that may
 * land on a different day than now (e.g. the +2h prediction crossing midnight).
 * @param {string | null | undefined} iso
 * @returns {string | null}
 */
export function formatDayClock(iso) {
  if (!iso) return null;
  try {
    return format(parseISO(iso), 'MMM d · h:mm a');
  } catch {
    return null;
  }
}

/**
 * Format an "HH:MM" wall-clock string (as returned for events) to "h:mm a".
 * @param {string | null | undefined} hhmm
 * @returns {string | null}
 */
export function formatEventTime(hhmm) {
  if (!hhmm) return null;
  const [h, m] = hhmm.split(':');
  const hour = Number(h);
  const minute = Number(m);
  if (Number.isNaN(hour) || Number.isNaN(minute)) return null;
  const period = hour >= 12 ? 'PM' : 'AM';
  const hour12 = hour % 12 === 0 ? 12 : hour % 12;
  return `${hour12}:${String(minute).padStart(2, '0')} ${period}`;
}

/**
 * Format an event date string "YYYY-MM-DD" as a calendar day header like
 * "Sat, Jun 14". Returns the raw value on parse failure.
 * @param {string} dateStr
 * @returns {string}
 */
export function formatEventDay(dateStr) {
  if (!dateStr) return '';
  try {
    return format(parseISO(dateStr), 'EEE, MMM d');
  } catch {
    return dateStr;
  }
}
