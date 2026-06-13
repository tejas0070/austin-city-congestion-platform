import { useState, useEffect } from 'react';
import { fetchUpcomingEvents, fetchEventsGeojson } from '../services/eventsService';

export function useEvents(days = 30) {
  const [events, setEvents] = useState([]);
  const [eventsGeojson, setEventsGeojson] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [list, geojson] = await Promise.all([
          fetchUpcomingEvents(days),
          fetchEventsGeojson(days),
        ]);
        if (!cancelled) {
          setEvents(list);
          setEventsGeojson(geojson);
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

  return { events, eventsGeojson, loading, error };
}
