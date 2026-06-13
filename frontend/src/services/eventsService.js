import api from './api';

export async function fetchUpcomingEvents(days = 30) {
  const { data } = await api.get('/api/events/upcoming', { params: { days } });
  return data;
}

export async function fetchEventsGeojson(days = 30) {
  const { data } = await api.get('/api/events/geojson', { params: { days } });
  return data;
}
