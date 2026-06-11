import { useState } from 'react';
import { useTrafficData } from './hooks/useTrafficData';
import { useEvents } from './hooks/useEvents';
import { useWeather } from './hooks/useWeather';
import MapContainer from './components/MapContainer';
import Sidebar from './components/Sidebar';
import LoadingOverlay from './components/LoadingOverlay';

const MAPBOX_TOKEN = process.env.REACT_APP_MAPBOX_TOKEN || '';

const INITIAL_LAYERS = {
  live_traffic: true,
  incidents: true,
  events: false,
};

export default function App() {
  const { liveTraffic, incidents, loading: trafficLoading } = useTrafficData();
  const { events } = useEvents();
  const { weather } = useWeather();

  const [layers, setLayers] = useState(INITIAL_LAYERS);

  function handleLayerToggle(key) {
    setLayers((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  const isLoading = trafficLoading;

  return (
    <div className="flex h-screen w-screen overflow-hidden">
      {isLoading && <LoadingOverlay />}
      <Sidebar
        events={events}
        weather={weather}
        layers={layers}
        onLayerToggle={handleLayerToggle}
      />
      <MapContainer
        liveTraffic={liveTraffic}
        incidents={incidents}
        mapboxToken={MAPBOX_TOKEN}
      />
    </div>
  );
}
