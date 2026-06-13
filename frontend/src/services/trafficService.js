import api from './api';

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
  });
  return data;
}
