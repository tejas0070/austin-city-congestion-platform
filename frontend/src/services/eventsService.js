import api from './api';

export async function fetchUpcomingEvents(days = 30) {
  const { data } = await api.get('/api/events/upcoming', { params: { days } });
  return data;
}
