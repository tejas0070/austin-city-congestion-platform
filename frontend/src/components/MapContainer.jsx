import { useEffect, useMemo, useRef } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import KeplerGl from '@kepler.gl/components';
import {
  addDataToMap,
  updateVisData,
  inputMapStyle,
  mapStyleChange,
  updateMap,
  layerConfigChange,
  layerVisualChannelConfigChange,
  removeDataset,
} from '@kepler.gl/actions';
import { processGeojson, processRowObject } from '@kepler.gl/processors';
import { AUSTIN_VIEWPORT, MIN_ZOOM, AUSTIN_GEO_BOUNDS } from '../constants/austinBounds';
import { buildDayFC, hourField } from '../utils/dayPrediction';
import { toISODate } from '../utils/calendar';

const SIDEBAR_WIDTH_PX = 320;
const MAP_ID = 'austin_traffic_map';

const CARTO_DARK = {
  id: 'carto_dark_matter',
  label: 'Carto Dark Matter',
  url: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
  icon: '',
  layerGroups: [],
};

// Shared green / yellow / red ramp keyed on congestion_index (0/1/2).
// customOrdinal + an explicit colorMap pins each index to a colour regardless
// of the data's range. A plain `quantize` derives thresholds from each batch's
// min/max, so a narrow batch (e.g. one hour that's mostly one level) collapses
// the domain and paints everything the last colour (red) — which also makes
// every animated hour look identical. The fixed map avoids both.
const CONGESTION_COLORS = ['#00C864', '#FFC800', '#DC3232'];
const CONGESTION_COLOR_RANGE = {
  name: 'Traffic Congestion',
  type: 'customOrdinal',
  category: 'Custom',
  colors: CONGESTION_COLORS,
  colorMap: [
    [0, '#00C864'],
    [1, '#FFC800'],
    [2, '#DC3232'],
  ],
};

// Fields shown when hovering a Predicted +2h segment (interval + confidence).
const PREDICTED_TOOLTIP_FIELDS = [
  { name: 'road_name' },
  { name: 'congestion_pct' },
  { name: 'congestion_low' },
  { name: 'congestion_high' },
  { name: 'confidence_pct' },
  { name: 'confidence_label' },
];

// Fields shown when hovering a Live Traffic segment. Explicitly set (rather than
// letting kepler auto-populate every property) so internal columns like
// segment_id / road_class never leak into the tooltip.
const LIVE_TOOLTIP_FIELDS = [
  { name: 'road_name' },
  { name: 'congestion_pct' },
  { name: 'congestion_level' },
];

// Dataset ids (must match the datasets pushed in the load effect).
const DATA = {
  live: 'corridors',
  predicted: 'corridors_predicted',
  dayPreview: 'corridors_day',
  events: 'events',
  incidents: 'incidents',
};

// Layer ids (kept stable so the visibility-sync effect can find them).
const LAYER = {
  live: 'corridors_live',
  predicted: 'corridors_pred',
  dayPreview: 'corridors_day',
  events: 'events_circles',
  incidents: 'incidents_icons',
};

// Hover-tooltip config applied wherever corridor datasets are added. Setting both
// datasets explicitly keeps segment_id/road_class out and ensures the predicted
// layer surfaces its interval + confidence fields.
const CORRIDOR_TOOLTIP_INTERACTION = {
  tooltip: {
    fieldsToShow: {
      [DATA.live]: LIVE_TOOLTIP_FIELDS,
      [DATA.predicted]: PREDICTED_TOOLTIP_FIELDS,
    },
    enabled: true,
  },
};

function corridorLineLayer(id, dataId, label, isVisible, field = 'congestion_index') {
  return {
    id,
    type: 'geojson',
    config: {
      dataId,
      label,
      isVisible,
      // processGeojson stores geometry in the `_geojson` column; a geojson
      // layer must bind to it or kepler leaves the dataset unconfigured.
      columns: { geojson: '_geojson' },
      // GeoJSON LineStrings are drawn with their STROKE, not their fill —
      // binding only colorField leaves every segment one solid colour. The
      // stroke color field is what actually drives the green/yellow/red ramp.
      strokeColorField: { name: field, type: 'integer' },
      strokeColorScale: 'customOrdinal',
      colorField: { name: field, type: 'integer' },
      colorScale: 'customOrdinal',
      visConfig: {
        thickness: 3,
        opacity: 0.9,
        stroked: true,
        strokeColorRange: CONGESTION_COLOR_RANGE,
        colorRange: CONGESTION_COLOR_RANGE,
      },
    },
  };
}

const EVENTS_LAYER = {
  id: LAYER.events,
  type: 'geojson',
  config: {
    dataId: DATA.events,
    label: 'Events',
    isVisible: true,
    columns: { geojson: '_geojson' },
    colorField: { name: 'category', type: 'string' },
    colorScale: 'ordinal',
    radiusField: { name: 'expected_attendance', type: 'real' },
    visConfig: {
      radius: 24,
      radiusRange: [12, 70],
      opacity: 0.55,
      stroked: true,
      filled: true,
      thickness: 2,
      colorRange: {
        name: 'Event Category',
        type: 'custom',
        category: 'Custom',
        colors: ['#3B82F6', '#A855F7', '#F59E0B'],
      },
    },
  },
};

const INCIDENTS_LAYER = {
  id: LAYER.incidents,
  type: 'icon',
  config: {
    dataId: DATA.incidents,
    label: 'Incidents',
    isVisible: true,
    columns: { lat: 'lat', lng: 'lng', icon: 'icon' },
    colorField: { name: 'severity', type: 'integer' },
    colorScale: 'quantize',
    visConfig: {
      radius: 30,
      opacity: 0.95,
      colorRange: {
        name: 'Incident Severity',
        type: 'custom',
        category: 'Custom',
        colors: ['#FACC15', '#FB923C', '#EF4444', '#B91C1C'],
      },
    },
  },
};

// The live map shows only imminent events (today + next 48h) so future games
// don't clutter "now". In day-preview it shows only that day's events instead.
const LIVE_EVENT_WINDOW_DAYS = 2;

/**
 * Filter the events FeatureCollection to the dates relevant for the current view.
 * - Preview mode (previewDate set): only events on that exact date.
 * - Live mode: events from today through +LIVE_EVENT_WINDOW_DAYS (inclusive).
 * Pure: returns a new FeatureCollection; input untouched.
 */
function eventsForView(fc, previewDate) {
  if (!fc?.features?.length) return fc;

  let keep;
  if (previewDate) {
    keep = (date) => date === previewDate;
  } else {
    const todayISO = toISODate(new Date());
    const end = new Date();
    end.setDate(end.getDate() + LIVE_EVENT_WINDOW_DAYS);
    const endISO = toISODate(end);
    keep = (date) => date >= todayISO && date <= endISO;
  }

  return { ...fc, features: fc.features.filter((f) => keep(f.properties?.date)) };
}

function incidentRows(incidents) {
  return (incidents?.features ?? []).map((f) => ({
    lat: f.geometry.coordinates[1],
    lng: f.geometry.coordinates[0],
    icon: 'place',
    incident_type: f.properties.incident_type,
    severity: f.properties.severity,
    description: f.properties.description,
  }));
}

export default function MapContainer({
  liveTraffic,
  corridors,
  corridorsPredicted,
  eventsGeojson,
  incidents,
  layers,
  previewDate,
  previewHour,
  daySegments,
  daySeries,
}) {
  const dispatch = useDispatch();
  const initializedRef = useRef(false);
  // Whether the styled +2h Predicted layer has been created yet. That feed
  // arrives after the live feed, so it often misses the initial addDataToMap.
  const predictedCreatedRef = useRef(false);
  // Which date's data is currently loaded as the day-preview dataset.
  const loadedPreviewDateRef = useRef(null);
  // Whether the (date-filtered) events dataset is currently loaded.
  const eventsLoadedRef = useRef(false);

  // Events relevant to the current view: the previewed day, or today + next 48h
  // on the live map. Recomputed when the feed or the viewed date changes.
  const mapEvents = useMemo(
    () => eventsForView(eventsGeojson, previewDate),
    [eventsGeojson, previewDate]
  );

  // The whole selected day as one FeatureCollection with a congestion column per
  // hour (cg_0..cg_23). Loaded once; scrubbing only swaps the layer's color field
  // (kepler can't update RowDataContainer rows in place, so we never replace data).
  const dayFC = useMemo(() => {
    if (!previewDate) return null;
    return buildDayFC(daySegments, daySeries);
  }, [previewDate, daySegments, daySeries]);

  const keplerMapState = useSelector((state) => state.keplerGl?.[MAP_ID]?.mapState);
  const keplerLayers = useSelector((state) => state.keplerGl?.[MAP_ID]?.visState?.layers);
  // Reactive "base map is up" flag (live layer exists). Stable boolean, so an
  // effect depending on it fires once on init rather than on every layer change.
  const isInitialized = useSelector((state) =>
    Boolean(state.keplerGl?.[MAP_ID]?.visState?.layers?.some((l) => l.id === LAYER.live))
  );
  // The day-preview dataset's resolved fields (each carries a valueAccessor that
  // kepler needs when recomputing a colour domain on a channel-field swap).
  const dayFields = useSelector(
    (state) => state.keplerGl?.[MAP_ID]?.visState?.datasets?.[DATA.dayPreview]?.fields
  );
  const zoom = keplerMapState?.zoom;
  const latitude = keplerMapState?.latitude;
  const longitude = keplerMapState?.longitude;

  // Keep the viewport clamped to Austin.
  useEffect(() => {
    if (zoom === undefined) return;
    const { minLon, maxLon, minLat, maxLat } = AUSTIN_GEO_BOUNDS;
    const update = {};
    let dirty = false;

    if (zoom < MIN_ZOOM) { update.zoom = MIN_ZOOM; dirty = true; }

    const axes = [
      { key: 'latitude', value: latitude, min: minLat, max: maxLat },
      { key: 'longitude', value: longitude, min: minLon, max: maxLon },
    ];
    for (const { key, value, min, max } of axes) {
      if (value < min || value > max) {
        update[key] = Math.max(min, Math.min(max, value));
        dirty = true;
      }
    }

    if (dirty) dispatch(updateMap(update));
  }, [zoom, latitude, longitude, dispatch]);

  // Load datasets + layer config once live segments arrive, then refresh on poll.
  // Gated on `corridors` only so a slow/failed prediction never blanks the map.
  useEffect(() => {
    if (!corridors?.features?.length) return;

    const datasets = [];
    const initialLayers = [];

    datasets.push({ info: { id: DATA.live, label: 'Live Traffic' }, data: processGeojson(corridors) });
    initialLayers.push(corridorLineLayer(LAYER.live, DATA.live, 'Live Traffic', true));

    const hasPredicted = corridorsPredicted?.features?.length > 0;
    if (hasPredicted) {
      datasets.push({ info: { id: DATA.predicted, label: 'Predicted +2h (ML)' }, data: processGeojson(corridorsPredicted) });
      initialLayers.push(corridorLineLayer(LAYER.predicted, DATA.predicted, 'Predicted +2h (ML)', false));
    }

    // Events are owned by the dedicated date-filtered effect below (they depend
    // on the viewed date), so they are intentionally not loaded here.

    const rows = incidentRows(incidents);
    if (rows.length > 0) {
      datasets.push({ info: { id: DATA.incidents, label: 'Incidents' }, data: processRowObject(rows) });
      initialLayers.push(INCIDENTS_LAYER);
    }

    if (!initializedRef.current) {
      dispatch(inputMapStyle(CARTO_DARK));
      dispatch(mapStyleChange('carto_dark_matter'));
      dispatch(
        addDataToMap({
          datasets,
          // readOnly hides kepler's own layer panel so users can't delete the
          // layers. Visibility is still controlled from our Sidebar toggles via
          // layerConfigChange, which keeps working in read-only mode.
          options: { centerMap: false, readOnly: true },
          config: {
            mapState: AUSTIN_VIEWPORT,
            visState: { layers: initialLayers },
            interactionConfig: CORRIDOR_TOOLTIP_INTERACTION,
          },
        })
      );
      // Force the viewport onto Austin deterministically (kepler occasionally
      // ignores the config mapState on cold start).
      dispatch(updateMap(AUSTIN_VIEWPORT));
      initializedRef.current = true;
      predictedCreatedRef.current = hasPredicted;
    } else {
      // The Predicted dataset is owned by the dedicated effect below so a poll
      // refresh never clobbers an active day-preview hour.
      const pollDatasets = datasets.filter((d) => d.info.id !== DATA.predicted);
      dispatch(updateVisData({ datasets: pollDatasets, options: { centerMap: false } }));
    }
  }, [liveTraffic, corridors, corridorsPredicted, incidents, dispatch]);

  // Create the styled +2h Predicted layer once its data is available (it usually
  // arrives after the initial addDataToMap). Row data can't be updated in place,
  // so this is create-once; the +2h snapshot is fixed for the session.
  useEffect(() => {
    if (!initializedRef.current || predictedCreatedRef.current) return;
    if (!corridorsPredicted?.features?.length) return;
    dispatch(addDataToMap({
      datasets: [{
        info: { id: DATA.predicted, label: 'Predicted +2h (ML)' },
        data: processGeojson(corridorsPredicted),
      }],
      // keepExistingConfig:true is REQUIRED. Without it, addDataToMap runs
      // resetMapConfigUpdater and wipes every existing layer, rebuilding only
      // this one — blanking the live/events/incidents layers.
      options: { centerMap: false, readOnly: true, autoCreateLayers: false, keepExistingConfig: true },
      config: {
        visState: { layers: [corridorLineLayer(LAYER.predicted, DATA.predicted, 'Predicted +2h (ML)', false)] },
        interactionConfig: CORRIDOR_TOOLTIP_INTERACTION,
      },
    }));
    predictedCreatedRef.current = true;
  }, [corridorsPredicted, dispatch]);

  // Load / refresh the events dataset, filtered to the current view's dates.
  // Reloads whenever the filtered set changes (new feed, or the viewed date
  // changes between live and a previewed day). Row data can't update in place,
  // so we remove + re-add; keepExistingConfig:true keeps the other layers.
  useEffect(() => {
    if (!isInitialized) return;

    if (eventsLoadedRef.current) {
      dispatch(removeDataset(DATA.events));
      eventsLoadedRef.current = false;
    }

    if (!mapEvents?.features?.length) return;

    dispatch(addDataToMap({
      datasets: [{ info: { id: DATA.events, label: 'Events' }, data: processGeojson(mapEvents) }],
      options: { centerMap: false, readOnly: true, autoCreateLayers: false, keepExistingConfig: true },
      config: { visState: { layers: [EVENTS_LAYER] } },
    }));
    eventsLoadedRef.current = true;
  }, [mapEvents, isInitialized, dispatch]);

  // Load (or swap) the day-preview dataset when a day is selected. The dataset
  // carries all 24 hours as columns; selecting a new day re-loads it (row data
  // can't be replaced in place). Exiting preview removes it.
  useEffect(() => {
    if (!initializedRef.current) return;

    if (!previewDate) {
      if (loadedPreviewDateRef.current !== null) {
        dispatch(removeDataset(DATA.dayPreview));
        loadedPreviewDateRef.current = null;
      }
      return;
    }

    if (!dayFC?.features?.length || loadedPreviewDateRef.current === previewDate) return;

    if (loadedPreviewDateRef.current !== null) {
      dispatch(removeDataset(DATA.dayPreview));
    }
    dispatch(addDataToMap({
      datasets: [{ info: { id: DATA.dayPreview, label: 'Day Preview' }, data: processGeojson(dayFC) }],
      // keepExistingConfig:true is REQUIRED — see the Predicted effect above.
      // Without it, selecting a day resets the whole map to just this layer.
      options: { centerMap: false, readOnly: true, autoCreateLayers: false, keepExistingConfig: true },
      config: {
        visState: {
          layers: [corridorLineLayer(LAYER.dayPreview, DATA.dayPreview, 'Day Preview', true, hourField(previewHour))],
        },
      },
    }));
    loadedPreviewDateRef.current = previewDate;
  }, [previewDate, dayFC, previewHour, dispatch]);

  // Scrub hours by swapping the day-preview layer's stroke color field — no data
  // replacement, so playback/scrubbing stays smooth and reliable. The field must
  // be the dataset's resolved field object (with its valueAccessor), not a plain
  // {name,type}, or kepler throws while recomputing the colour domain.
  useEffect(() => {
    if (!previewDate || loadedPreviewDateRef.current !== previewDate) return;
    const layer = keplerLayers?.find((l) => l.id === LAYER.dayPreview);
    if (!layer) return;
    const fieldName = hourField(previewHour);
    if (layer.config?.strokeColorField?.name === fieldName) return;
    const field = dayFields?.find((f) => f.name === fieldName);
    if (!field) return;
    dispatch(layerVisualChannelConfigChange(layer, { strokeColorField: field }, 'strokeColor'));
  }, [previewHour, previewDate, keplerLayers, dayFields, dispatch]);

  // Sync kepler layer visibility to the sidebar toggles, accounting for preview
  // mode: the day-preview layer stands in for the +2h Predicted layer while a
  // day is being explored.
  useEffect(() => {
    if (!keplerLayers || !layers) return;
    const inPreview = !!previewDate;
    // Live and Predicted share identical geometry, so showing both stacks two
    // layers on the same roads and the top one (Live) captures every hover —
    // hiding the predicted interval/confidence tooltip. When Predicted is the
    // active forecast view, suppress Live so its segments are the ones hovered.
    const predictedActive = layers.predicted && !inPreview;
    const desired = {
      [LAYER.live]: layers.live_traffic && !predictedActive,
      [LAYER.predicted]: layers.predicted && !inPreview,
      [LAYER.dayPreview]: layers.predicted && inPreview,
      [LAYER.events]: layers.events,
      [LAYER.incidents]: layers.incidents,
    };
    for (const layer of keplerLayers) {
      if (layer.id in desired && layer.config.isVisible !== desired[layer.id]) {
        dispatch(layerConfigChange(layer, { isVisible: desired[layer.id] }));
      }
    }
  }, [layers, keplerLayers, previewDate, dispatch]);

  return (
    <div className="relative flex-1 h-full">
      <KeplerGl
        id={MAP_ID}
        mapboxApiAccessToken=""
        width={window.innerWidth - SIDEBAR_WIDTH_PX}
        height={window.innerHeight}
      />
      {/* Cover kepler's default "add data / upload" empty state during the
          cold-start window, until the first dataset creates the live layer. */}
      {!isInitialized && (
        <div
          style={{ zIndex: 1000 }}
          className="absolute inset-0 flex items-center justify-center bg-[#0b0b0d]"
        >
          <div className="flex flex-col items-center gap-3 text-gray-300">
            <span className="h-8 w-8 animate-spin rounded-full border-2 border-gray-700 border-t-blue-500" />
            <p className="text-sm font-medium tracking-wide">Loading Austin traffic…</p>
          </div>
        </div>
      )}
    </div>
  );
}
