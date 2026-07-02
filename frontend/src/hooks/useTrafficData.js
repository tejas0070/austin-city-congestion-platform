import { useState, useEffect, useRef } from 'react';
import { fetchLiveTraffic, fetchHistoricalTraffic, fetchIncidents, fetchCorridors, fetchPredicted } from '../services/trafficService';

const POLL_INTERVAL_MS = 2 * 60 * 1000;

export function useTrafficData() {
  const [liveTraffic, setLiveTraffic] = useState(null);
  const [historical, setHistorical] = useState(null);
  const [incidents, setIncidents] = useState(null);
  const [corridors, setCorridors] = useState(null);
  const [corridorsPredicted, setCorridorsPredicted] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  async function load() {
    // Each dataset is independent: one slow/failed call must not blank the map.
    const settle = async (fn, setter, label, primary = false) => {
      try {
        setter(await fn());
        // The live corridors layer is what paints the map. Clear the first-load
        // spinner the moment it lands so the slower predicted (ML) / historical
        // (DB) fetches finishing in the background don't keep the overlay up over
        // an already-rendered map (visible on cold free-tier backends).
        if (primary) setLoading(false);
        return true;
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn(`[useTrafficData] ${label} failed:`, err?.message ?? err);
        return false;
      }
    };

    const results = await Promise.allSettled([
      settle(fetchCorridors, setCorridors, 'live segments', true),
      settle(() => fetchPredicted(2), setCorridorsPredicted, 'predicted segments'),
      settle(fetchIncidents, setIncidents, 'incidents'),
      settle(fetchLiveTraffic, setLiveTraffic, 'live points'),
      settle(fetchHistoricalTraffic, setHistorical, 'historical'),
    ]);

    const anyOk = results.some((r) => r.status === 'fulfilled' && r.value);
    setError(anyOk ? null : 'Could not reach the traffic API. Is the backend running on :8000?');
    // Catch-all: clear the spinner even if the primary corridors fetch failed,
    // so a backend hiccup never leaves the overlay stuck forever.
    setLoading(false);
  }

  useEffect(() => {
    load();
    intervalRef.current = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(intervalRef.current);
  }, []);

  return { liveTraffic, historical, incidents, corridors, corridorsPredicted, loading, error };
}
