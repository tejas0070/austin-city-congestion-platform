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
