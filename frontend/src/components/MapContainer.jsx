import { useEffect, useRef } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import KeplerGl from '@kepler.gl/components';
import {
  addDataToMap,
  updateVisData,
  inputMapStyle,
  mapStyleChange,
  updateMap,
  layerConfigChange,
} from '@kepler.gl/actions';
import { processGeojson, processRowObject } from '@kepler.gl/processors';
import { AUSTIN_VIEWPORT, MIN_ZOOM, AUSTIN_GEO_BOUNDS } from '../constants/austinBounds';

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
const CONGESTION_COLOR_RANGE = {
  name: 'Traffic Congestion',
  type: 'custom',
  category: 'Custom',
  colors: ['#00C864', '#FFC800', '#DC3232'],
};

// Dataset ids (must match the datasets pushed in the load effect).
const DATA = {
  live: 'corridors',
  predicted: 'corridors_predicted',
  events: 'events',
  incidents: 'incidents',
};

// Layer ids (kept stable so the visibility-sync effect can find them).
const LAYER = {
  live: 'corridors_live',
  predicted: 'corridors_pred',
  events: 'events_circles',
  incidents: 'incidents_icons',
};

// App `layers` toggle key -> kepler layer id.
const VISIBILITY_MAP = {
  live_traffic: LAYER.live,
  predicted: LAYER.predicted,
  events: LAYER.events,
  incidents: LAYER.incidents,
};

function corridorLineLayer(id, dataId, label, isVisible) {
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
      strokeColorField: { name: 'congestion_index', type: 'integer' },
      strokeColorScale: 'quantize',
      colorField: { name: 'congestion_index', type: 'integer' },
      colorScale: 'quantize',
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
}) {
  const dispatch = useDispatch();
  const initializedRef = useRef(false);

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

    if (corridorsPredicted?.features?.length > 0) {
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
    } else {
      dispatch(updateVisData({ datasets, options: { centerMap: false } }));
    }
  }, [liveTraffic, corridors, corridorsPredicted, eventsGeojson, incidents, dispatch]);

  // Sync kepler layer visibility to the sidebar toggle state.
  useEffect(() => {
    if (!keplerLayers || !layers) return;
    for (const [key, layerId] of Object.entries(VISIBILITY_MAP)) {
      const layer = keplerLayers.find((l) => l.id === layerId);
      if (layer && layer.config.isVisible !== layers[key]) {
        dispatch(layerConfigChange(layer, { isVisible: layers[key] }));
      }
    }
  }, [layers, keplerLayers, dispatch]);

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
