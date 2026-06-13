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
    const settle = async (fn, setter, label) => {
      try {
        setter(await fn());
        return true;
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn(`[useTrafficData] ${label} failed:`, err?.message ?? err);
        return false;
      }
    };

    const results = await Promise.allSettled([
      settle(fetchCorridors, setCorridors, 'live segments'),
      settle(() => fetchPredicted(2), setCorridorsPredicted, 'predicted segments'),
      settle(fetchIncidents, setIncidents, 'incidents'),
      settle(fetchLiveTraffic, setLiveTraffic, 'live points'),
      settle(fetchHistoricalTraffic, setHistorical, 'historical'),
    ]);

    const anyOk = results.some((r) => r.status === 'fulfilled' && r.value);
    setError(anyOk ? null : 'Could not reach the traffic API. Is the backend running on :8000?');
    setLoading(false);
  }

  useEffect(() => {
    load();
    intervalRef.current = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(intervalRef.current);
  }, []);

  return { liveTraffic, historical, incidents, corridors, corridorsPredicted, loading, error };
}
