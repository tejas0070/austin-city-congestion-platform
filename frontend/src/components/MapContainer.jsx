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
  interactionConfigChange,
  removeDataset,
} from '@kepler.gl/actions';
import { processGeojson, processRowObject } from '@kepler.gl/processors';
import { AUSTIN_VIEWPORT, MIN_ZOOM, AUSTIN_GEO_BOUNDS } from '../constants/austinBounds';
import { buildDayFC, hourField } from '../utils/dayPrediction';
import { toISODate } from '../utils/calendar';
import {
  withLiveTooltips,
  withPredictedTooltips,
  withEventTooltips,
  withDayTooltips,
  incidentRows,
} from '../utils/mapTooltips';

// The kepler canvas fills the whole screen; the sidebar console floats over it.
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

// Hover-tooltip field lists, keyed to the user-facing property labels produced by
// the `with*Tooltips` transforms (see utils/mapTooltips.js). They are set
// explicitly — rather than letting kepler auto-populate every column — so
// internal/binding columns (segment_id, road_class, congestion_index, the icon
// layer's lat/lng/icon, the day layer's cg_* hours) never leak into the tooltip.
const toFields = (names) => names.map((name) => ({ name, format: null }));

const LIVE_TOOLTIP_FIELDS = toFields(['Road', 'Congestion', 'Status']);
const PREDICTED_TOOLTIP_FIELDS = toFields([
  'Road',
  'Congestion',
  'Forecast Range',
  'Confidence',
  'Forecast Time',
]);
const EVENT_TOOLTIP_FIELDS = toFields([
  'Event',
  'Venue',
  'Date',
  'Time',
  'Category',
  'Attendance',
]);
const INCIDENT_TOOLTIP_FIELDS = toFields(['Type', 'Description', 'Severity']);
const DAY_TOOLTIP_FIELDS = toFields(['Road']);

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

// Humanize a raw column id into a Title Case label for the kepler legend
// (e.g. "congestion_index" → "Congestion Index", "severity" → "Severity").
function humanizeFieldName(name) {
  return name
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// Give every processed-dataset field a humanized `displayName` so the kepler
// legend reads "Congestion Index" instead of the raw binding column name. The
// field `name` (kepler's lookup key) is left untouched; only the label changes.
// kepler resolves a layer's colorField to the dataset's field object by name
// (vis-state-merger.validateSavedVisualChannels), so the displayName set here
// is what the legend renders.
function withFormattedFieldNames(data) {
  if (!data?.fields) return data;
  return {
    ...data,
    fields: data.fields.map((field) => ({
      ...field,
      displayName: humanizeFieldName(field.displayName || field.name),
    })),
  };
}

// Build a kepler dataset entry from a FeatureCollection, returning null when
// processGeojson can't produce a valid table — e.g. features are present but
// their geometry is missing/unsupported after the tooltip transforms. Handing
// kepler a null `data` makes validateInputData fail and raises its top-right
// "Failed to create a new dataset due to data verification errors" toast, so
// callers must skip a null entry rather than push it.
function geojsonDataset(id, label, fc) {
  const data = processGeojson(fc);
  if (!data) {
    console.warn(`[map] skipping dataset "${id}": no usable geometry to render`);
    return null;
  }
  return { info: { id, label }, data: withFormattedFieldNames(data) };
}

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
    colorField: { name: 'Category', type: 'string' },
    colorScale: 'ordinal',
    radiusField: { name: 'Attendance', type: 'real' },
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
  // Whether the incidents dataset/layer is currently loaded.
  const incidentsLoadedRef = useRef(false);

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
  // Current basemap style. Toggling Predicted runs another addDataToMap, which
  // resets kepler's map style off our custom CARTO dark basemap to its default
  // (a blank/white canvas). We watch this and snap it back.
  const keplerStyleType = useSelector((state) => state.keplerGl?.[MAP_ID]?.mapStyle?.styleType);

  // Keep the CARTO dark basemap pinned. Anything that resets kepler's map style
  // — the init gate not having run, a hot-reload, or the addDataToMap that
  // creates the Predicted layer — would otherwise leave a blank/white canvas.
  // Snapping styleType back makes the dark basemap self-healing, so the map can
  // never get stuck white. Re-asserting the same style is a no-op, so no loop.
  useEffect(() => {
    if (keplerStyleType === 'carto_dark_matter') return;
    dispatch(inputMapStyle(CARTO_DARK));
    dispatch(mapStyleChange('carto_dark_matter'));
  }, [keplerStyleType, dispatch]);
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
  // kepler's hover-tooltip interaction, plus a stable key of the currently
  // loaded dataset ids. Together they drive the effect that pins our clean
  // tooltip fields onto every dataset as they load (addDataToMap's
  // interactionConfig is ignored once the map exists, and keepExistingConfig
  // makes kepler auto-add every column for newly loaded datasets).
  const tooltipInteraction = useSelector(
    (state) => state.keplerGl?.[MAP_ID]?.visState?.interactionConfig?.tooltip
  );
  const loadedDatasetKey = useSelector((state) => {
    const datasets = state.keplerGl?.[MAP_ID]?.visState?.datasets;
    return datasets ? Object.keys(datasets).sort().join(',') : '';
  });
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

    // Live is the dataset the map is gated on; if it can't be processed there is
    // nothing to show yet, so bail and let the next poll retry rather than
    // initialising kepler with an empty/invalid dataset.
    const live = geojsonDataset(DATA.live, 'Live Traffic', withLiveTooltips(corridors));
    if (!live) return;

    const datasets = [live];
    const initialLayers = [corridorLineLayer(LAYER.live, DATA.live, 'Live Traffic', true)];

    const predicted = corridorsPredicted?.features?.length
      ? geojsonDataset(DATA.predicted, 'Predicted +2h (ML)', withPredictedTooltips(corridorsPredicted))
      : null;
    if (predicted) {
      datasets.push(predicted);
      initialLayers.push(corridorLineLayer(LAYER.predicted, DATA.predicted, 'Predicted +2h (ML)', false));
    }

    // Events and Incidents are owned by dedicated effects below. Incidents in
    // particular arrives in its own render (a separate fetch), so loading it
    // here would only create its icon layer on the lucky races where it beat the
    // big corridors fetch. The dedicated effect creates the layer whenever the
    // incidents feed shows up, so the icons are always present.

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
      // Only mark Predicted as created if it was actually added above; if its
      // data was missing/invalid, the dedicated effect below retries it.
      predictedCreatedRef.current = Boolean(predicted);
    } else {
      // The Predicted dataset is owned by the dedicated effect below so a poll
      // refresh never clobbers an active day-preview hour.
      // updateVisData takes POSITIONAL args (datasets, options) — passing a
      // single { datasets, options } object makes kepler treat that wrapper as a
      // dataset with undefined data, which fails validation and raises the
      // "Failed to create a new dataset due to data verification errors" toast
      // on every poll (and skips the real refresh).
      const pollDatasets = datasets.filter((d) => d.info.id !== DATA.predicted);
      dispatch(updateVisData(pollDatasets, { centerMap: false }));
    }
  }, [liveTraffic, corridors, corridorsPredicted, dispatch]);

  // Create the styled +2h Predicted layer once its data is available (it usually
  // arrives after the initial addDataToMap). Row data can't be updated in place,
  // so this is create-once; the +2h snapshot is fixed for the session.
  useEffect(() => {
    if (!initializedRef.current || predictedCreatedRef.current) return;
    if (!corridorsPredicted?.features?.length) return;
    const predicted = geojsonDataset(DATA.predicted, 'Predicted +2h (ML)', withPredictedTooltips(corridorsPredicted));
    if (!predicted) return; // retry on the next feed rather than toast
    dispatch(addDataToMap({
      datasets: [predicted],
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

  // Pin our user-facing tooltip fields onto every dataset as it loads.
  // addDataToMap's interactionConfig is ignored once the map exists, and
  // keepExistingConfig makes kepler auto-add EVERY column for a newly loaded
  // dataset (which would leak the event `id`, the day layer's cg_* hours, the
  // incident lat/lng/icon, etc.). Re-running whenever the loaded-dataset set
  // changes lets us re-assert the clean fields after events/day-preview reload.
  // Idempotent: only dispatches when a present dataset's fields differ.
  useEffect(() => {
    if (!tooltipInteraction || !loadedDatasetKey) return;
    const wanted = {
      [DATA.live]: LIVE_TOOLTIP_FIELDS,
      [DATA.predicted]: PREDICTED_TOOLTIP_FIELDS,
      [DATA.dayPreview]: DAY_TOOLTIP_FIELDS,
      [DATA.events]: EVENT_TOOLTIP_FIELDS,
      [DATA.incidents]: INCIDENT_TOOLTIP_FIELDS,
    };
    const sameFields = (a, b) =>
      Array.isArray(a) && a.length === b.length && a.every((f, i) => f.name === b[i].name);

    const current = tooltipInteraction.config?.fieldsToShow || {};
    const next = { ...current };
    let changed = false;
    for (const id of loadedDatasetKey.split(',')) {
      if (wanted[id] && !sameFields(current[id], wanted[id])) {
        next[id] = wanted[id];
        changed = true;
      }
    }
    if (!changed) return;

    dispatch(interactionConfigChange({
      ...tooltipInteraction,
      enabled: true,
      config: { ...tooltipInteraction.config, fieldsToShow: next },
    }));
  }, [tooltipInteraction, loadedDatasetKey, dispatch]);

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

    const eventsDataset = geojsonDataset(DATA.events, 'Events', withEventTooltips(mapEvents));
    if (!eventsDataset) return;

    dispatch(addDataToMap({
      datasets: [eventsDataset],
      options: { centerMap: false, readOnly: true, autoCreateLayers: false, keepExistingConfig: true },
      config: { visState: { layers: [EVENTS_LAYER] } },
    }));
    eventsLoadedRef.current = true;
  }, [mapEvents, isInitialized, dispatch]);

  // Load / refresh the Incidents dataset + icon layer once the map is up. The
  // incidents feed arrives in its own render (a separate fetch), so owning it in
  // a dedicated effect — rather than the corridors-gated init effect — means the
  // icon layer is created whenever incidents show up, regardless of which feed
  // wins the load race. Row data can't update in place, so each refresh
  // remove + re-adds; keepExistingConfig:true keeps the other layers intact.
  useEffect(() => {
    if (!isInitialized) return;

    if (incidentsLoadedRef.current) {
      dispatch(removeDataset(DATA.incidents));
      incidentsLoadedRef.current = false;
    }

    const rows = incidentRows(incidents);
    if (rows.length === 0) return;

    const incidentsData = processRowObject(rows);
    if (!incidentsData) return;

    dispatch(addDataToMap({
      datasets: [{ info: { id: DATA.incidents, label: 'Incidents' }, data: withFormattedFieldNames(incidentsData) }],
      options: { centerMap: false, readOnly: true, autoCreateLayers: false, keepExistingConfig: true },
      config: { visState: { layers: [INCIDENTS_LAYER] } },
    }));
    incidentsLoadedRef.current = true;
  }, [incidents, isInitialized, dispatch]);

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

    const dayDataset = geojsonDataset(DATA.dayPreview, 'Day Preview', withDayTooltips(dayFC));
    if (!dayDataset) return;

    if (loadedPreviewDateRef.current !== null) {
      dispatch(removeDataset(DATA.dayPreview));
    }
    dispatch(addDataToMap({
      datasets: [dayDataset],
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
    <div className="absolute inset-0 h-full w-full">
      <KeplerGl
        id={MAP_ID}
        mapboxApiAccessToken=""
        width={window.innerWidth}
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
            <span className="h-8 w-8 animate-spin rounded-full border-2 border-gray-700 border-t-violet" />
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-gray-400">Loading Austin traffic…</p>
          </div>
        </div>
      )}
    </div>
  );
}
