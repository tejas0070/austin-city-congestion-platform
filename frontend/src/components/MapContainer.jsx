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

  // The whole selected day as one FeatureCollection with a congestion column per
  // hour (cg_0..cg_23). Loaded once; scrubbing only swaps the layer's color field
  // (kepler can't update RowDataContainer rows in place, so we never replace data).
  const dayFC = useMemo(() => {
    if (!previewDate) return null;
    return buildDayFC(daySegments, daySeries);
  }, [previewDate, daySegments, daySeries]);

  const keplerMapState = useSelector((state) => state.keplerGl?.[MAP_ID]?.mapState);
  const keplerLayers = useSelector((state) => state.keplerGl?.[MAP_ID]?.visState?.layers);
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

    if (eventsGeojson?.features?.length > 0) {
      datasets.push({ info: { id: DATA.events, label: 'Events' }, data: processGeojson(eventsGeojson) });
      initialLayers.push(EVENTS_LAYER);
    }

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
  }, [liveTraffic, corridors, corridorsPredicted, eventsGeojson, incidents, dispatch]);

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
      options: { centerMap: false, readOnly: true, autoCreateLayers: false },
      config: {
        visState: { layers: [corridorLineLayer(LAYER.predicted, DATA.predicted, 'Predicted +2h (ML)', false)] },
      },
    }));
    predictedCreatedRef.current = true;
  }, [corridorsPredicted, dispatch]);

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
      options: { centerMap: false, readOnly: true, autoCreateLayers: false },
      config: {
        visState: {
          layers: [corridorLineLayer(LAYER.dayPreview, DATA.dayPreview, 'Day Preview', true, hourField(previewHour))],
        },
      },
    }));
    loadedPreviewDateRef.current = previewDate;
  }, [previewDate, dayFC, previewHour, dispatch]);

  // Scrub hours by swapping the day-preview layer's stroke color field — no data
  // replacement, so playback/scrubbing stays smooth and reliable.
  useEffect(() => {
    if (!previewDate || loadedPreviewDateRef.current !== previewDate) return;
    const layer = keplerLayers?.find((l) => l.id === LAYER.dayPreview);
    if (!layer) return;
    const field = hourField(previewHour);
    if (layer.config?.strokeColorField?.name === field) return;
    dispatch(layerVisualChannelConfigChange(
      layer,
      { strokeColorField: { name: field, type: 'integer' } },
      'strokeColor',
    ));
  }, [previewHour, previewDate, keplerLayers, dispatch]);

  // Sync kepler layer visibility to the sidebar toggles, accounting for preview
  // mode: the day-preview layer stands in for the +2h Predicted layer while a
  // day is being explored.
  useEffect(() => {
    if (!keplerLayers || !layers) return;
    const inPreview = !!previewDate;
    const desired = {
      [LAYER.live]: layers.live_traffic,
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
    </div>
  );
}
