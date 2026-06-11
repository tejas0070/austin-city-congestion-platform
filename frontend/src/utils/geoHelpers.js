export function isValidCoord(lat, lng) {
  return (
    typeof lat === 'number' &&
    typeof lng === 'number' &&
    lat >= -90 &&
    lat <= 90 &&
    lng >= -180 &&
    lng <= 180
  );
}

export function featureCollectionToRows(featureCollection) {
  if (!featureCollection?.features) return [];
  return featureCollection.features.map((f) => ({
    ...f.properties,
    latitude: f.geometry?.coordinates?.[1],
    longitude: f.geometry?.coordinates?.[0],
  }));
}
