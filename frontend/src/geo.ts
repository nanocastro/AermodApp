export function destinationPoint(latitude: number, longitude: number, distance: number, bearingDeg: number): [number, number] {
  const earthRadius = 6371000;
  const angularDistance = distance / earthRadius;
  const bearing = bearingDeg * Math.PI / 180;
  const latitudeRadians = latitude * Math.PI / 180;
  const longitudeRadians = longitude * Math.PI / 180;
  const targetLatitude = Math.asin(
    Math.sin(latitudeRadians) * Math.cos(angularDistance)
    + Math.cos(latitudeRadians) * Math.sin(angularDistance) * Math.cos(bearing),
  );
  const targetLongitude = longitudeRadians + Math.atan2(
    Math.sin(bearing) * Math.sin(angularDistance) * Math.cos(latitudeRadians),
    Math.cos(angularDistance) - Math.sin(latitudeRadians) * Math.sin(targetLatitude),
  );
  return [targetLatitude * 180 / Math.PI, targetLongitude * 180 / Math.PI];
}
