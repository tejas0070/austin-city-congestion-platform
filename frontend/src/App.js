import { useState, useEffect } from 'react';
import { useTrafficData } from './hooks/useTrafficData';
import { useEvents } from './hooks/useEvents';
import { useWeather } from './hooks/useWeather';
import { useDayPrediction } from './hooks/useDayPrediction';
import { useWeekConfidence } from './hooks/useWeekConfidence';
import { useModelInfo } from './hooks/useModelInfo';
import MapContainer from './components/MapContainer';
import Sidebar from './components/Sidebar';
import LoadingOverlay from './components/LoadingOverlay';
import EventCalendar from './components/EventCalendar';
import TimeSliderPanel from './components/TimeSliderPanel';
import IntroSplash from './components/IntroSplash';
import { toISODate } from './utils/calendar';

const SPLASH_SEEN_KEY = 'atx_splash_seen';


const INITIAL_LAYERS = {
  live_traffic: true,
  predicted: false,
  events: true,
  incidents: true,
};

const PREVIEW_HORIZON_DAYS = 90;
const PLAY_INTERVAL_MS = 600;
const HOURS_PER_DAY = 24;
const DEFAULT_PREVIEW_HOUR = 8;

function dateFromISO(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d);
}

export default function App() {
  const { liveTraffic, corridors, corridorsPredicted, incidents, loading: trafficLoading } = useTrafficData();
  const { events, eventsGeojson } = useEvents(PREVIEW_HORIZON_DAYS);
  const { weather } = useWeather();

  // Show the intro splash once per browser session; the dashboard mounts behind
  // it so traffic data prefetches while the animation plays.
  const [showSplash, setShowSplash] = useState(
    () => sessionStorage.getItem(SPLASH_SEEN_KEY) !== '1'
  );

  const [layers, setLayers] = useState(INITIAL_LAYERS);
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [previewDate, setPreviewDate] = useState(null);
  const [previewHour, setPreviewHour] = useState(DEFAULT_PREVIEW_HOUR);
  const [isPlaying, setIsPlaying] = useState(false);

  const todayISO = toISODate(new Date());
  // The model panel is always on: it reflects the previewed day, or today in
  // live view. Both day and week predictions key off this anchor.
  const anchorISO = previewDate ?? todayISO;
  const day = useDayPrediction(anchorISO);
  const week = useWeekConfidence(anchorISO);
  const model = useModelInfo();

  const maxDate = new Date();
  maxDate.setDate(maxDate.getDate() + PREVIEW_HORIZON_DAYS);
  const maxISO = toISODate(maxDate);

  const dayCard = {
    date: anchorISO,
    confidenceAvg: day.confidenceAvg,
    confidenceLabel: day.confidenceLabel,
    congestionAvg: day.congestionAvg,
    congestionLevel: day.congestionLevel,
    hours: day.hours,
    loading: day.loading,
  };

  // Auto-advance the hour while playing.
  useEffect(() => {
    if (!isPlaying || !previewDate || day.loading || day.hours.length === 0) return undefined;
    const id = setInterval(() => {
      setPreviewHour((h) => (h + 1) % HOURS_PER_DAY);
    }, PLAY_INTERVAL_MS);
    return () => clearInterval(id);
  }, [isPlaying, previewDate, day.loading, day.hours.length]);

  function handleLayerToggle(key) {
    setLayers((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      // Live Traffic (now) and Predicted (a different time) are mutually
      // exclusive — enabling one disables the other so they never overlap.
      if (key === 'live_traffic' && next.live_traffic) next.predicted = false;
      if (key === 'predicted' && next.predicted) next.live_traffic = false;
      return next;
    });
  }

  function handleSelectDay(iso) {
    setPreviewDate(iso);
    setPreviewHour(iso === todayISO ? new Date().getHours() : DEFAULT_PREVIEW_HOUR);
    setIsPlaying(false);
    setCalendarOpen(false);
    // Preview shows a non-"now" time, so swap Live off and Predicted on.
    setLayers((prev) => ({ ...prev, predicted: true, live_traffic: false }));
  }

  function handleExitPreview() {
    setPreviewDate(null);
    setIsPlaying(false);
    // Back to the live default.
    setLayers((prev) => ({ ...prev, predicted: false, live_traffic: true }));
  }

  function handleEnter() {
    sessionStorage.setItem(SPLASH_SEEN_KEY, '1');
    setShowSplash(false);
  }

  const isLoading = trafficLoading;

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-paper">
      {showSplash && <IntroSplash onEnter={handleEnter} />}
      {/* While the splash is up it's the only curtain — data prefetches behind
          the spiral. The loading overlay is for the post-Enter wait, if any. */}
      {isLoading && !showSplash && <LoadingOverlay />}
      {/* Map is the full-screen base; the sidebar console floats over it. */}
      <MapContainer
        liveTraffic={liveTraffic}
        corridors={corridors}
        corridorsPredicted={corridorsPredicted}
        eventsGeojson={eventsGeojson}
        incidents={incidents}
        layers={layers}
        previewDate={previewDate}
        previewHour={previewHour}
        daySegments={day.segments}
        daySeries={day.series}
      />
      <Sidebar
        events={events}
        weather={weather}
        layers={layers}
        onLayerToggle={handleLayerToggle}
        liveUpdatedAt={corridors?.generated_at}
        predictedFor={previewDate ? null : corridorsPredicted?.predicted_for}
        onOpenCalendar={() => setCalendarOpen(true)}
        modelAccuracyPct={model.accuracyPct}
        modelAccuracyLoading={model.loading}
        dayCard={dayCard}
        week={week}
        selectedISO={anchorISO}
        onSelectDay={handleSelectDay}
      />

      {calendarOpen && (
        <EventCalendar
          events={events}
          onSelectDay={handleSelectDay}
          onClose={() => setCalendarOpen(false)}
          minISO={todayISO}
          maxISO={maxISO}
          initialDate={previewDate ? dateFromISO(previewDate) : new Date()}
        />
      )}

      {previewDate && (
        <TimeSliderPanel
          dateISO={previewDate}
          hours={day.hours}
          currentHour={previewHour}
          isPlaying={isPlaying}
          onTogglePlay={() => setIsPlaying((p) => !p)}
          onSelectHour={setPreviewHour}
          onClose={handleExitPreview}
          weatherSource={day.weatherSource}
          confidenceAvg={day.confidenceAvg}
          confidenceLabel={day.confidenceLabel}
          loading={day.loading}
          error={day.error}
        />
      )}
    </div>
  );
}
