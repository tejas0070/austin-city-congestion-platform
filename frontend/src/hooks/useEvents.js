import { useState, useEffect } from 'react';
import { fetchUpcomingEvents } from '../services/eventsService';

export function useEvents(days = 30) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await fetchUpcomingEvents(days);
        if (!cancelled) {
          setEvents(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message ?? 'Failed to load events');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [days]);

  return { events, loading, error };
}
