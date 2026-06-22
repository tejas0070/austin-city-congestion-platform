import api from './api';

// City-wide ML predictions are CPU-heavy (thousands of segments, and the week
// path computes 7 days). They far exceed the default 10s client timeout on a
// cold cache, so these calls get generous per-request timeouts.
const PREDICTION_TIMEOUT_MS = 60000;
const WEEK_TIMEOUT_MS = 120000;

export async function fetchLiveTraffic() {
  const { data } = await api.get('/api/traffic/live');
  return data;
}

export async function fetchHistoricalTraffic(hour = null) {
  const params = hour !== null ? { hour } : {};
  const { data } = await api.get('/api/traffic/historical', { params });
  return data;
}

export async function fetchIncidents() {
  const { data } = await api.get('/api/traffic/incidents');
  return data;
}

export async function fetchCorridors() {
  const { data } = await api.get('/api/traffic/corridors');
  return data;
}

export async function fetchPredicted(hoursAhead = 2, includeEvents = true) {
  const { data } = await api.get('/api/traffic/corridors/predicted', {
    params: { hours_ahead: hoursAhead, include_events: includeEvents },
    timeout: PREDICTION_TIMEOUT_MS,
  });
  return data;
}

/**
 * Fetch the whole-day predicted congestion for a date ("YYYY-MM-DD"): geometry
 * once plus a per-hour congestion-index matrix.
 * @param {string} date
 * @param {boolean} includeEvents
 */
export async function fetchDayPrediction(date, includeEvents = true) {
  const { data } = await api.get('/api/traffic/corridors/day', {
    params: { date, include_events: includeEvents },
    timeout: PREDICTION_TIMEOUT_MS,
  });
  return data;
}

/**
 * Fetch whole-week forecast confidence for the 7 days starting at `start`
 * ("YYYY-MM-DD"): 7 daily averages plus an overall week average.
 * @param {string} start
 * @param {boolean} includeEvents
 */
export async function fetchWeekConfidence(start, includeEvents = true) {
  const { data } = await api.get('/api/traffic/corridors/week', {
    params: { start, include_events: includeEvents },
    timeout: WEEK_TIMEOUT_MS,
  });
  return data;
}

/**
 * Fetch trained-model metadata (availability, segment count, and quality stats
 * such as empirical interval coverage). Used to surface the model's accuracy.
 */
export async function fetchModelInfo() {
  const { data } = await api.get('/api/traffic/model/info', { timeout: 30000 });
  return data;
}
