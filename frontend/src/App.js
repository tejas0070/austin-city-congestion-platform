import { useState } from 'react';
import { useTrafficData } from './hooks/useTrafficData';
import { useEvents } from './hooks/useEvents';
import { useWeather } from './hooks/useWeather';
import MapContainer from './components/MapContainer';
import Sidebar from './components/Sidebar';
import LoadingOverlay from './components/LoadingOverlay';


const INITIAL_LAYERS = {
  live_traffic: true,
  predicted: false,
  events: true,
  incidents: true,
};

export default function App() {
  const { liveTraffic, corridors, corridorsPredicted, incidents, loading: trafficLoading } = useTrafficData();
  const { events, eventsGeojson } = useEvents();
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
        liveUpdatedAt={corridors?.generated_at}
        predictedFor={corridorsPredicted?.predicted_for}
      />
      <MapContainer
        liveTraffic={liveTraffic}
        corridors={corridors}
        corridorsPredicted={corridorsPredicted}
        eventsGeojson={eventsGeojson}
        incidents={incidents}
        layers={layers}
      />
    </div>
  );
}
