import { useState, useEffect, useRef } from 'react';
import { fetchLiveTraffic, fetchHistoricalTraffic, fetchIncidents } from '../services/trafficService';

const POLL_INTERVAL_MS = 2 * 60 * 1000;

export function useTrafficData() {
  const [liveTraffic, setLiveTraffic] = useState(null);
  const [historical, setHistorical] = useState(null);
  const [incidents, setIncidents] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  async function load() {
    try {
      const [live, hist, inc] = await Promise.all([
        fetchLiveTraffic(),
        fetchHistoricalTraffic(),
        fetchIncidents(),
      ]);
      setLiveTraffic(live);
      setHistorical(hist);
      setIncidents(inc);
      setError(null);
    } catch (err) {
      setError(err.message ?? 'Failed to load traffic data');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    intervalRef.current = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(intervalRef.current);
  }, []);

  return { liveTraffic, historical, incidents, loading, error };
}
