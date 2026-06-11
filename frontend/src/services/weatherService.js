import api from './api';

export async function fetchCurrentWeather() {
  const { data } = await api.get('/api/weather/current');
  return data;
}
