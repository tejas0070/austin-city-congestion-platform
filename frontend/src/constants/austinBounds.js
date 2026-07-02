export const AUSTIN_BOUNDS = {
  longitude: -97.7431,
  latitude: 30.2672,
  zoom: 11.5,
};

// Passed to kepler's mapState — must contain only numeric viewport fields.
// (width/height are managed by the map container; putting strings like '100%'
// here corrupts kepler's viewport and makes it fall back to a default location.)
export const AUSTIN_VIEWPORT = {
  longitude: -97.7431,
  latitude: 30.2672,
  zoom: 11.5,
  pitch: 0,
  bearing: 0,
};

// Minimum zoom that keeps the view within the greater Austin metro area.
// At zoom 10, a 1400px-wide viewport covers ~160 km — Texas but not the whole USA.
export const MIN_ZOOM = 10;

// Hard geographic boundary for the greater Austin metro area.
// Users cannot pan the map center outside this box.
export const AUSTIN_GEO_BOUNDS = {
  minLon: -98.1,
  maxLon: -97.4,
  minLat: 30.0,
  maxLat: 30.7,
};
