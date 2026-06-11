import { useState, useEffect, useRef } from 'react';
import { fetchCurrentWeather } from '../services/weatherService';

const POLL_INTERVAL_MS = 15 * 60 * 1000;

export function useWeather() {
  const [weather, setWeather] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  async function load() {
    try {
      const data = await fetchCurrentWeather();
      setWeather(data);
      setError(null);
    } catch (err) {
      setError(err.message ?? 'Failed to load weather');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    intervalRef.current = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(intervalRef.current);
  }, []);

  return { weather, loading, error };
}
