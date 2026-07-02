/**
 * User-facing map tooltips.
 *
 * kepler.gl renders a feature's raw property KEYS as tooltip labels, so the
 * backend's machine-friendly columns (`road_name`, `incident_type`,
 * `congestion_pct`, an event `id`, an ISO `predicted_for`…) would otherwise leak
 * straight into the hover card. These helpers rewrite each feature's properties
 * into clean, human-readable labels (Title Case, no underscores, friendly times)
 * BEFORE the data reaches `processGeojson` / `processRowObject`.
 *
 * The backend GeoJSON contract is intentionally left untouched (real data drops
 * in without code changes); all of this presentation lives on the frontend.
 *
 * Every function is pure and immutable: it returns new objects and never
 * mutates its input. Columns the map layers bind to for colour/size
 * (`congestion_index`, `severity`, `cg_*`, point `lat`/`lng`/`icon`) are
 * preserved so styling keeps working.
 */

/**
 * Format a clock time as e.g. "6:00PM" (matches the requested display format —
 * no space, no leading zero on the hour).
 *
 * Accepts "HH:MM", "HH:MM:SS", or an ISO datetime ("2026-06-20T18:00").
 * Returns '' when the value is missing or unparseable.
 *
 * @param {string} value
 * @returns {string}
 */
export function formatClock(value) {
  if (!value) return '';
  const str = String(value);
  const timePart = str.includes('T') ? str.split('T')[1] : str;
  const match = timePart.match(/^(\d{1,2}):(\d{2})/);
  if (!match) return '';
  const hour = Number(match[1]);
  const minutes = match[2];
  if (Number.isNaN(hour) || hour < 0 || hour > 23) return '';
  const period = hour < 12 ? 'AM' : 'PM';
  const hour12 = hour % 12 || 12;
  return `${hour12}:${minutes}${period}`;
}

/**
 * Format an ISO date ("2026-06-14") as "Jun 14, 2026". Falls back to the raw
 * input when it can't be parsed, and '' when empty.
 *
 * @param {string} iso
 * @returns {string}
 */
export function formatEventDate(iso) {
  if (!iso) return '';
  const date = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

/**
 * Title-case a snake_case / space-separated string: "incident_type" -> "Incident
 * Type", "accident" -> "Accident". Returns '' for empty input.
 *
 * @param {string} value
 * @returns {string}
 */
export function titleCase(value) {
  if (!value) return '';
  return String(value)
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(' ');
}

// Maps the backend's colour code to a plain-English congestion status.
const STATUS_BY_LEVEL = { green: 'Light', yellow: 'Moderate', red: 'Heavy' };

/** Plain-English congestion status for a green/yellow/red level. */
export function congestionStatus(level) {
  return STATUS_BY_LEVEL[level] || 'Unknown';
}

// Maps the backend's 1–4 severity scale to a plain-English word.
const SEVERITY_WORDS = { 1: 'Minor', 2: 'Moderate', 3: 'Major', 4: 'Severe' };

/** Plain-English severity for a 1–4 incident severity. */
export function severityLabel(severity) {
  return SEVERITY_WORDS[severity] || 'Unknown';
}

/** Round a 0–100 percentage to a whole-number "47%" string ('' when missing). */
function pct(value) {
  if (value === null || value === undefined || value === '') return '';
  return `${Math.round(Number(value))}%`;
}

/**
 * Return a new FeatureCollection with each feature's properties replaced by
 * `fn(properties)`. Passes non-collections (and empty ones) through unchanged.
 *
 * @param {{features?: Array}} fc
 * @param {(props: object) => object} fn
 */
function mapFeatureProps(fc, fn) {
  if (!fc?.features?.length) return fc;
  return {
    ...fc,
    features: fc.features.map((feature) => ({
      ...feature,
      properties: fn(feature.properties || {}),
    })),
  };
}

/**
 * Live Traffic hover labels. Keeps `congestion_index` for the colour ramp;
 * drops internal columns (segment_id / road_class).
 */
export function withLiveTooltips(fc) {
  return mapFeatureProps(fc, (p) => ({
    congestion_index: p.congestion_index,
    Road: p.road_name || 'Road',
    Congestion: pct(p.congestion_pct),
    Status: congestionStatus(p.congestion_level),
  }));
}

/**
 * Predicted +2h hover labels. Folds the low/high interval into one "Forecast
 * Range" and confidence into one line, and shows the forecast clock time.
 * Keeps `congestion_index` for the colour ramp.
 */
export function withPredictedTooltips(fc) {
  return mapFeatureProps(fc, (p) => ({
    congestion_index: p.congestion_index,
    Road: p.road_name || 'Road',
    Congestion: pct(p.congestion_pct),
    'Forecast Range':
      p.congestion_low != null && p.congestion_high != null
        ? `${Math.round(p.congestion_low)}–${Math.round(p.congestion_high)}%`
        : '',
    Confidence:
      p.confidence_pct != null
        ? p.confidence_label
          ? `${p.confidence_pct}% (${p.confidence_label})`
          : `${p.confidence_pct}%`
        : '',
    ...(p.event_uplift_pct != null && p.event_uplift_pct > 0
      ? { 'Event Impact': `+${Math.round(p.event_uplift_pct)}%` }
      : {}),
    'Forecast Time': formatClock(p.predicted_for),
  }));
}

/**
 * Events hover labels. Drops the internal `id` / `days_until` / `source`, shows
 * the start time as "7:30PM" and a readable date. Keeps `Category` (string) and
 * `Attendance` (number) — the Events layer binds colour to Category and circle
 * size to Attendance.
 */
export function withEventTooltips(fc) {
  return mapFeatureProps(fc, (p) => ({
    Event: p.name || '',
    Venue: p.venue || '',
    Date: formatEventDate(p.date),
    Time: formatClock(p.time),
    Category: p.category || 'Other',
    Attendance: p.expected_attendance ?? 0,
  }));
}

/**
 * Day-preview hover label. Adds a clean `Road` label while preserving every
 * `cg_*` hour column (the layer binds its colour to the scrubbed hour) plus the
 * other static props.
 */
export function withDayTooltips(fc) {
  return mapFeatureProps(fc, (p) => ({ ...p, Road: p.road_name || 'Road' }));
}

/**
 * Incident rows for kepler's icon layer. Keeps `lat`/`lng`/`icon` (layer
 * columns) and numeric `severity` (colour binding); adds human labels. The
 * incident tooltip is pinned to Type / Description / Severity so the point
 * coordinates and icon column never show.
 */
export function incidentRows(incidents) {
  return (incidents?.features ?? []).map((feature) => {
    const p = feature.properties || {};
    return {
      lat: feature.geometry.coordinates[1],
      lng: feature.geometry.coordinates[0],
      icon: 'place',
      severity: p.severity,
      Type: titleCase(p.incident_type),
      Description: p.description || '',
      Severity: severityLabel(p.severity),
    };
  });
}
