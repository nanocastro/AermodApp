import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { toPng } from "html-to-image";
import { contours as createContours } from "d3-contour";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Clock3,
  Download,
  Factory,
  FileCode2,
  Gauge,
  KeyRound,
  LoaderCircle,
  Maximize2,
  MapPinned,
  RefreshCw,
  ShieldCheck,
  Table2,
  Wind,
  X,
} from "lucide-react";
import { api } from "./api";
import { destinationPoint } from "./geo";
import { CircleMarker, LayerGroup, LayersControl, MapContainer, Polygon, Polyline, Popup, TileLayer, WMSTileLayer } from "react-leaflet";
import { isHourlyDefinition, isHourlyResult, isMultiSourceHourlyDefinition, isMultiSourceHourlyResult, type Artifact, type ConcentrationPoint, type HourlyResult, type HourlyScenarioDefinition, type MultiSourceHourlyResult, type MultiSourceHourlyScenarioDefinition, type Run, type Scenario, type ScreeningScenarioDefinition } from "./types";

function format(value: number, digits = 4): string {
  return new Intl.NumberFormat("es-AR", { maximumFractionDigits: digits }).format(value);
}

function duration(run: Run): string {
  if (!run.started_at || !run.finished_at) return "—";
  const seconds = Math.max(0, (new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000);
  return `${seconds.toFixed(1)} s`;
}

function relativePoint(latitude: number, longitude: number, eastM: number, northM: number): [number, number] {
  const longitudeScale = 111320 * Math.cos(latitude * Math.PI / 180);
  return [latitude + northM / 111320, longitude + eastM / longitudeScale];
}

function ConcentrationChart({ points, maximumDistance }: { points: ConcentrationPoint[]; maximumDistance: number }) {
  const width = 760;
  const height = 280;
  const margin = { left: 58, right: 22, top: 22, bottom: 42 };
  const sorted = [...points].sort((a, b) => a.distance_m - b.distance_m);
  const minX = Math.min(...sorted.map((point) => point.distance_m));
  const maxX = Math.max(...sorted.map((point) => point.distance_m));
  const maxY = Math.max(...sorted.map((point) => point.concentration_1h_ug_m3)) * 1.08;
  const x = (value: number) => margin.left + ((value - minX) / (maxX - minX || 1)) * (width - margin.left - margin.right);
  const y = (value: number) => height - margin.bottom - (value / (maxY || 1)) * (height - margin.top - margin.bottom);
  const path = sorted.map((point, index) => `${index ? "L" : "M"}${x(point.distance_m).toFixed(2)},${y(point.concentration_1h_ug_m3).toFixed(2)}`).join(" ");
  const maxPoint = sorted.reduce((best, point) => point.concentration_1h_ug_m3 > best.concentration_1h_ug_m3 ? point : best, sorted[0]);
  const xTicks = [minX, minX + (maxX - minX) / 2, maxX];
  const yTicks = [0, maxY / 2, maxY];
  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Concentración de una hora por distancia">
        <defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#2688ba" stopOpacity=".3" /><stop offset="1" stopColor="#8dd8f5" stopOpacity=".04" /></linearGradient></defs>
        {yTicks.map((tick) => <g key={tick}><line x1={margin.left} x2={width - margin.right} y1={y(tick)} y2={y(tick)} className="chart-grid" /><text x={margin.left - 10} y={y(tick) + 4} textAnchor="end" className="chart-label">{format(tick, 2)}</text></g>)}
        {xTicks.map((tick) => <text key={tick} x={x(tick)} y={height - 14} textAnchor="middle" className="chart-label">{format(tick, 0)} m</text>)}
        <path d={`${path} L${x(maxX)},${height - margin.bottom} L${x(minX)},${height - margin.bottom} Z`} fill="url(#area)" />
        <path d={path} fill="none" stroke="#247eae" strokeWidth="3" strokeLinejoin="round" />
        <line x1={x(maximumDistance)} x2={x(maximumDistance)} y1={margin.top} y2={height - margin.bottom} stroke="#9c6b1e" strokeDasharray="5 5" />
        <circle cx={x(maxPoint.distance_m)} cy={y(maxPoint.concentration_1h_ug_m3)} r="6" fill="#fff" stroke="#9c6b1e" strokeWidth="3" />
        <text x={x(maxPoint.distance_m)} y={y(maxPoint.concentration_1h_ug_m3) - 13} textAnchor="middle" className="chart-peak">MÁXIMO</text>
        <text x={16} y={height / 2} transform={`rotate(-90 16 ${height / 2})`} textAnchor="middle" className="axis-title">Concentración (µg/m³)</text>
      </svg>
    </div>
  );
}

function ContextMap({ distance }: { distance: number }) {
  return (
    <div className="context-map">
      <svg viewBox="0 0 360 250" role="img" aria-label="Mapa conceptual del screening">
        <rect width="360" height="250" rx="10" fill="#edf7fc" />
        <path d="M0 55 L360 15 M0 120 L360 80 M0 190 L360 145 M70 0 L20 250 M170 0 L120 250 M270 0 L220 250" stroke="#d4e7f2" strokeWidth="1" />
        {[42, 76, 108].map((radius) => <circle key={radius} cx="170" cy="125" r={radius} fill="none" stroke="#7fb9d6" strokeDasharray="4 5" />)}
        <line x1="170" y1="125" x2="278" y2="125" stroke="#9c6b1e" strokeWidth="2" />
        <circle cx="170" cy="125" r="10" fill="#247eae" /><circle cx="170" cy="125" r="16" fill="none" stroke="#247eae" opacity=".25" />
        <circle cx="278" cy="125" r="7" fill="#fff" stroke="#9c6b1e" strokeWidth="3" />
        <text x="170" y="151" textAnchor="middle" className="map-label">FUENTE</text>
        <text x="278" y="105" textAnchor="middle" className="map-peak">MÁXIMO</text>
        <text x="278" y="157" textAnchor="middle" className="map-distance">{format(distance, 0)} m</text>
      </svg>
      <p>Representación radial conceptual. En screening, el máximo no está asociado a una dirección cronológica del viento.</p>
    </div>
  );
}

function concentrationColor(value: number, maximum: number): string {
  const ratio = maximum > 0 ? Math.max(0, Math.min(1, value / maximum)) : 0;
  const hue = 210 - ratio * 200;
  return `hsl(${hue} 70% 43%)`;
}

type MaximumImpact = {
  windDirectionDeg: number;
  distanceM: number;
  concentration: number;
};

const SMN_STATIONS = [
  { code: "87344", name: "Córdoba Aero", latitude: -31.32, longitude: -64.22, elevation: 474 },
  { code: "87345", name: "Córdoba Observatorio", latitude: -31.40, longitude: -64.18, elevation: 425 },
  { code: "87418", name: "Mendoza Aero", latitude: -32.83, longitude: -68.78, elevation: 705 },
  { code: "87420", name: "Mendoza Observatorio", latitude: -32.89, longitude: -68.87, elevation: 827 },
];

function radialRing(latitude: number, longitude: number, radius: number): [number, number][] {
  return Array.from({ length: 73 }, (_, index) => destinationPoint(latitude, longitude, radius, index * 5));
}

function buildingPolygon(latitude: number, longitude: number, vertices: { east_m: number; north_m: number }[]): [number, number][] {
  const longitudeScale = 111320 * Math.cos(latitude * Math.PI / 180);
  return vertices.map((vertex) => [latitude + vertex.north_m / 111320, longitude + vertex.east_m / longitudeScale]);
}

function ConcentrationMap({ latitude, longitude, points, buildings = [], maximumImpacts = [], meteorology, expanded = false }: { latitude: number; longitude: number; points: ConcentrationPoint[]; buildings?: ScreeningScenarioDefinition["downwash"]["buildings"]; maximumImpacts?: MaximumImpact[]; meteorology: ScreeningScenarioDefinition["meteorology"]; expanded?: boolean }) {
  const position: [number, number] = [latitude, longitude];
  const maximum = Math.max(...points.map((point) => point.concentration_1h_ug_m3));
  const sorted = [...points].sort((a, b) => a.distance_m - b.distance_m);
  const stride = Math.max(1, Math.floor(sorted.length / 14));
  const bands = sorted.filter((_, index) => index % stride === 0 || index === sorted.length - 1);
  const nearbyStations = SMN_STATIONS.filter((station) => Math.abs(station.latitude - latitude) < 2 && Math.abs(station.longitude - longitude) < 2);
  return (
    <MapContainer center={position} zoom={expanded ? 14 : 13} scrollWheelZoom className={`leaflet-map${expanded ? " expanded-map" : ""}`} attributionControl={expanded}>
        <LayersControl position="topright">
          <LayersControl.BaseLayer checked name="Calles"><TileLayer crossOrigin attribution='&copy; OpenStreetMap &copy; CARTO' url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" /></LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Relieve"><TileLayer crossOrigin attribution='Map data: &copy; OpenStreetMap contributors, SRTM | Map style: &copy; OpenTopoMap (CC-BY-SA)' url="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png" maxZoom={17} /></LayersControl.BaseLayer>
          <LayersControl.Overlay name="ESA WorldCover 2021"><WMSTileLayer crossOrigin url="https://services.terrascope.be/wms/v2" layers="WORLDCOVER_2021_MAP" format="image/png" transparent opacity={0.58} attribution="ESA WorldCover 2021 / Terrascope" /></LayersControl.Overlay>
          <LayersControl.Overlay checked name="Envolvente de concentración"><LayerGroup>{bands.map((point, index) => {
          const color = concentrationColor(point.concentration_1h_ug_m3, maximum);
          const outer = radialRing(latitude, longitude, point.distance_m);
          const innerRadius = index === 0 ? 0 : bands[index - 1].distance_m;
          const positions = innerRadius > 0
            ? [outer, radialRing(latitude, longitude, innerRadius).reverse()]
            : outer;
          return <Polygon key={`${point.distance_m}-${point.concentration_1h_ug_m3}`} positions={positions} pathOptions={{ color, fillColor: color, fillOpacity: 0.27, opacity: 0.62, weight: 1 }}><Popup><strong>{format(point.concentration_1h_ug_m3, 5)} µg/m³</strong><br />Distancia: {format(innerRadius, 0)}–{format(point.distance_m, 0)} m</Popup></Polygon>;
        })}</LayerGroup></LayersControl.Overlay>
          <LayersControl.Overlay checked name="Máxima concentración"><LayerGroup>{maximumImpacts.map((impact) => {
          const plumeDirection = (impact.windDirectionDeg + 180) % 360;
          const target = destinationPoint(latitude, longitude, impact.distanceM, plumeDirection);
          return <Fragment key={`${impact.windDirectionDeg}-${impact.distanceM}`}><Polyline positions={[position, target]} pathOptions={{ color: "#9c6b1e", weight: 3, dashArray: "8 6", opacity: .9 }} /><CircleMarker center={target} radius={9} pathOptions={{ color: "#ffffff", fillColor: "#9c6b1e", fillOpacity: 1, weight: 3 }}><Popup><strong>Máxima concentración</strong><br />{format(impact.concentration, 5)} µg/m³<br />Distancia: {format(impact.distanceM, 0)} m<br />Viento desde: {format(impact.windDirectionDeg, 0)}°<br />Impacto hacia: {format(plumeDirection, 0)}°</Popup></CircleMarker></Fragment>;
        })}</LayerGroup></LayersControl.Overlay>
          {!!buildings.length && <LayersControl.Overlay checked name="Edificios / downwash"><LayerGroup>{buildings.map((building) => <Polygon key={building.building_id} positions={buildingPolygon(latitude, longitude, building.vertices)} pathOptions={{ color: "#5b3218", fillColor: "#c47a35", fillOpacity: .72, weight: 2 }}><Popup><strong>Edificio {building.building_id}</strong><br />Altura: {format(building.height_m, 1)} m<br />Geometría procesada por BPIPPRM</Popup></Polygon>)}</LayerGroup></LayersControl.Overlay>}
          <LayersControl.Overlay checked name="Parámetros de superficie"><LayerGroup><CircleMarker center={position} radius={8} pathOptions={{ color: "#ffffff", fillColor: "#247eae", fillOpacity: 1, weight: 3 }}><Popup><strong>Fuente y parámetros locales</strong><br />{latitude.toFixed(6)}, {longitude.toFixed(6)}<br />Albedo: {format(meteorology.albedo, 4)}<br />Bowen: {format(meteorology.bowen_ratio, 4)}<br />Rugosidad z₀: {format(meteorology.surface_roughness_m, 4)} m</Popup></CircleMarker></LayerGroup></LayersControl.Overlay>
          {!!nearbyStations.length && <LayersControl.Overlay name="Estaciones SMN"><LayerGroup>{nearbyStations.map((station) => <CircleMarker key={station.code} center={[station.latitude, station.longitude]} radius={7} pathOptions={{ color: "#ffffff", fillColor: "#28689b", fillOpacity: 1, weight: 2 }}><Popup><strong>{station.name}</strong><br />OMM {station.code}<br />Elevación: {station.elevation} m s.n.m.<br />Fuente: red de observación SMN</Popup></CircleMarker>)}</LayerGroup></LayersControl.Overlay>}
        </LayersControl>
      </MapContainer>
  );
}

function GeoreferencedMap({ latitude, longitude, points, buildings = [], maximumImpacts = [], meteorology }: { latitude: number; longitude: number; points: ConcentrationPoint[]; buildings?: ScreeningScenarioDefinition["downwash"]["buildings"]; maximumImpacts?: MaximumImpact[]; meteorology: ScreeningScenarioDefinition["meteorology"] }) {
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    if (!expanded) return;
    const close = (event: KeyboardEvent) => event.key === "Escape" && setExpanded(false);
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [expanded]);
  return (
    <div className="context-map georeferenced-map">
      <div className="map-frame">
        <ConcentrationMap latitude={latitude} longitude={longitude} points={points} buildings={buildings} maximumImpacts={maximumImpacts} meteorology={meteorology} />
        <button className="expand-map" data-export-ignore onClick={() => setExpanded(true)} title="Ampliar mapa"><Maximize2 size={16} /> Ampliar</button>
      </div>
      <div className="concentration-legend"><span>Baja</span><i /><span>Alta</span><b>Concentración máxima radial de 1 h</b></div>
      <p>Los anillos son una envolvente radial conservadora. La línea ocre marca el rayo a sotavento y el punto donde AERMOD encontró el máximo; no representa una trayectoria cronológica.</p>
      {expanded && <div className="map-modal" role="dialog" aria-modal="true" aria-label="Mapa ampliado de concentraciones"><div className="map-modal-panel"><header><div><p className="eyebrow">RESULTADOS ESPACIALES</p><h2>Concentraciones radiales superpuestas</h2></div><button onClick={() => setExpanded(false)} aria-label="Cerrar mapa"><X size={22} /></button></header><ConcentrationMap latitude={latitude} longitude={longitude} points={points} buildings={buildings} maximumImpacts={maximumImpacts} meteorology={meteorology} expanded /><div className="concentration-legend modal-legend"><span>Baja</span><i /><span>Alta</span><b>Envolvente de screening · µg/m³</b></div></div></div>}
    </div>
  );
}

function HourlyContourMap({ latitude, longitude, result, directionStep, sources, buildings = [] }: { latitude: number; longitude: number; result: HourlyResult | MultiSourceHourlyResult; directionStep: number; sources?: MultiSourceHourlyResult["source_positions"]; buildings?: ScreeningScenarioDefinition["downwash"]["buildings"] }) {
  const surface = useMemo(() => {
    const points = result.maximum_1h_by_receptor ?? [];
    const radii = [...new Set(points.map((point) => Math.round(Math.hypot(point.x_m, point.y_m))))].sort((a, b) => a - b);
    const lookup = new Map<string, number>();
    for (const point of points) {
      const radius = Math.round(Math.hypot(point.x_m, point.y_m));
      const bearing = Math.round((Math.atan2(point.x_m, point.y_m) * 180 / Math.PI + 360) % 360 / directionStep) % Math.round(360 / directionStep);
      lookup.set(`${radius}:${bearing}`, point.concentration_1h_ug_m3);
    }
    const angularCount = Math.round(360 / directionStep);
    const atRing = (radius: number, bearing: number) => {
      const angular = (bearing / directionStep + angularCount) % angularCount;
      const lower = Math.floor(angular) % angularCount;
      const upper = (lower + 1) % angularCount;
      const fraction = angular - Math.floor(angular);
      const low = lookup.get(`${radius}:${lower}`) ?? 0;
      const high = lookup.get(`${radius}:${upper}`) ?? low;
      return low + (high - low) * fraction;
    };
    const interpolate = (eastM: number, northM: number) => {
      const radius = Math.hypot(eastM, northM);
      if (!radii.length || radius > radii[radii.length - 1]) return 0;
      const bearing = (Math.atan2(eastM, northM) * 180 / Math.PI + 360) % 360;
      if (radius <= radii[0]) return atRing(radii[0], bearing) * radius / radii[0];
      const upperIndex = radii.findIndex((candidate) => candidate >= radius);
      const lowerRadius = radii[upperIndex - 1];
      const upperRadius = radii[upperIndex];
      const fraction = (radius - lowerRadius) / (upperRadius - lowerRadius);
      return atRing(lowerRadius, bearing) * (1 - fraction) + atRing(upperRadius, bearing) * fraction;
    };
    const size = 81;
    const maximumRadius = radii[radii.length - 1] || 1;
    const cell = maximumRadius * 2 / (size - 1);
    const values = Array.from({ length: size * size }, (_, index) => {
      const column = index % size;
      const row = Math.floor(index / size);
      return interpolate(-maximumRadius + column * cell, maximumRadius - row * cell);
    });
    const maximum = result.maximum_1h.concentration_ug_m3;
    const thresholds = [0.15, 0.3, 0.45, 0.6, 0.75, 0.9].map((fraction) => maximum * fraction);
    const generated = createContours().size([size, size]).thresholds(thresholds)(values);
    const polygons = generated.flatMap((contour, levelIndex) => contour.coordinates.flatMap((polygon, polygonIndex) => ({
      key: `${levelIndex}-${polygonIndex}`,
      level: contour.value,
      color: concentrationColor(contour.value, maximum),
      positions: polygon.map((ring) => ring.map(([gridX, gridY]) => relativePoint(
        latitude,
        longitude,
        -maximumRadius + gridX * cell,
        maximumRadius - gridY * cell,
      ))),
    })));
    return { polygons, thresholds, maximumRadius, maximum };
  }, [directionStep, latitude, longitude, result]);
  const source: [number, number] = [latitude, longitude];
  const sourceMarkers = sources?.length ? sources : [{ source_id: "Fuente puntual", latitude_deg: latitude, longitude_deg: longitude, x_m: 0, y_m: 0 }];
  const maximumPosition = relativePoint(latitude, longitude, result.maximum_1h.x_m, result.maximum_1h.y_m);
  const boundsRadius = Math.max(
    surface.maximumRadius,
    ...sourceMarkers.map((item) => Math.hypot(item.x_m, item.y_m) * 1.15),
  );
  const bounds: [[number, number], [number, number]] = [
    relativePoint(latitude, longitude, -boundsRadius, -boundsRadius),
    relativePoint(latitude, longitude, boundsRadius, boundsRadius),
  ];
  return <div className="context-map georeferenced-map hourly-contour-map"><div className="map-frame"><MapContainer bounds={bounds} scrollWheelZoom className="leaflet-map" attributionControl><LayersControl position="topright"><LayersControl.BaseLayer checked name="Calles"><TileLayer crossOrigin attribution='&copy; OpenStreetMap &copy; CARTO' url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" /></LayersControl.BaseLayer><LayersControl.BaseLayer name="Relieve"><TileLayer crossOrigin attribution='Map data: &copy; OpenStreetMap contributors, SRTM | Map style: &copy; OpenTopoMap (CC-BY-SA)' url="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png" maxZoom={17} /></LayersControl.BaseLayer><LayersControl.Overlay checked name="Contornos máximos 1 h"><LayerGroup>{surface.polygons.map((polygon) => <Polygon key={polygon.key} positions={polygon.positions} pathOptions={{ color: polygon.color, fillColor: polygon.color, fillOpacity: 0.3, opacity: 0.8, weight: 1.4 }}><Popup><strong>Contorno {format(polygon.level, 3)} µg/m³</strong><br />Máximo 1 h por receptor</Popup></Polygon>)}</LayerGroup></LayersControl.Overlay>{buildings.length > 0 && <LayersControl.Overlay checked name="Edificios / downwash"><LayerGroup>{buildings.map((building) => <Polygon key={building.building_id} positions={buildingPolygon(latitude, longitude, building.vertices)} pathOptions={{ color: "#5b3218", fillColor: "#c47a35", fillOpacity: .72, weight: 2 }}><Popup><strong>{building.building_id}</strong><br />Altura {format(building.height_m, 1)} m<br />BPIPPRM/PRIME horario</Popup></Polygon>)}</LayerGroup></LayersControl.Overlay>}<LayersControl.Overlay checked name="Fuentes y máximo global"><LayerGroup>{sourceMarkers.map((item) => <CircleMarker key={item.source_id} center={[item.latitude_deg, item.longitude_deg]} radius={7} pathOptions={{ color: "#fff", fillColor: "#174f3d", fillOpacity: 1, weight: 3 }}><Popup><strong>{item.source_id}</strong>{item.elevation_m != null && <><br />Cota AERMAP {format(item.elevation_m, 1)} m</>}</Popup></CircleMarker>)}<Polyline positions={[source, maximumPosition]} pathOptions={{ color: "#8b3f18", weight: 3, dashArray: "8 6" }} /><CircleMarker center={maximumPosition} radius={9} pathOptions={{ color: "#fff", fillColor: "#a54016", fillOpacity: 1, weight: 3 }}><Popup><strong>Máximo global 1 h</strong><br />{format(result.maximum_1h.concentration_ug_m3, 5)} µg/m³<br />{format(result.maximum_1h.distance_m, 0)} m · rumbo {format(result.maximum_1h.bearing_deg, 0)}°</Popup></CircleMarker></LayerGroup></LayersControl.Overlay></LayersControl></MapContainer></div><div className="contour-scale">{surface.thresholds.map((threshold) => <span key={threshold}><i style={{ background: concentrationColor(threshold, surface.maximum) }} />{format(threshold, 2)}</span>)}<b>µg/m³</b></div><p>Contornos interpolados de la envolvente anual de máximos de 1 hora por receptor. Los puntos pueden alcanzar su máximo en horas distintas; no es una instantánea simultánea.</p></div>;
}

function HourlyCompleted({ run, scenario, result, artifacts, error, repeating, onBack, onCredentials, onRepeat }: { run: Run; scenario: Scenario & { definition: HourlyScenarioDefinition | MultiSourceHourlyScenarioDefinition }; result: HourlyResult | MultiSourceHourlyResult; artifacts: Artifact[]; error: string; repeating: boolean; onBack: () => void; onCredentials: () => void; onRepeat: () => void }) {
  const multiDefinition = isMultiSourceHourlyDefinition(scenario.definition) ? scenario.definition : null;
  const singleDefinition = isHourlyDefinition(scenario.definition) ? scenario.definition : null;
  const multiResult = isMultiSourceHourlyResult(result) ? result : null;
  const multi = multiResult != null && multiDefinition != null;
  const hourlyDownwash = !multi && Boolean(result.downwash_enabled);
  const station = result.station === "cordoba-aero" ? "Córdoba Aero · OMM 87344" : "Mendoza Aero · OMM 87418";
  const hourEnding = new Date(result.maximum_1h.hour_ending_local).toLocaleString("es-AR", {
    dateStyle: "medium", timeStyle: "short", timeZone: "America/Argentina/Buenos_Aires",
  });
  const condition = result.maximum_condition;
  const latitude = multiResult?.domain_center_latitude_deg ?? singleDefinition?.source.latitude_deg;
  const longitude = multiResult?.domain_center_longitude_deg ?? singleDefinition?.source.longitude_deg;
  const directPeriods = result.period_maxima?.length ? result.period_maxima : [{
    averaging_period: "1h" as const,
    concentration_ug_m3: result.maximum_1h.concentration_ug_m3,
    aermod_timestamp: result.maximum_1h.aermod_timestamp,
    hour_ending_local: result.maximum_1h.hour_ending_local,
    x_m: result.maximum_1h.x_m,
    y_m: result.maximum_1h.y_m,
    distance_m: result.maximum_1h.distance_m,
    bearing_deg: result.maximum_1h.bearing_deg,
  }];
  const directMaximum = Math.max(...directPeriods.map((period) => period.concentration_ug_m3));
  const periodLabel = (period: string) => period === "annual" ? "Anual" : period === "1h" ? "1 hora" : period.replace("h", " horas");
  return (
    <div className="results-shell">
      <header className="topbar"><button className="back-dashboard" onClick={onBack}><ArrowLeft size={18} /> Escenarios</button><div className="brand-center"><Clock3 size={20} /> AERMOD {multi ? "Multifuente" : "Horario"}</div><button className="credentials-button wizard-credentials" onClick={onCredentials}><KeyRound size={15} /> Credenciales</button><span className="completed-label"><CheckCircle2 size={14} /> COMPLETADA</span></header>
      <main className="results-main">
        <section className="results-heading"><div><p className="eyebrow">RESULTADOS HORARIOS {multi ? "MULTIFUENTE" : "OBSERVADOS"}</p><h1>{scenario.name}</h1><p>{station} · {result.year} · {multiResult ? `${multiResult.source_count} fuentes · ` : ""}{scenario.definition.dispersion_mode === "rural" ? "Rural" : "Urbano"}</p></div><button className="secondary" onClick={onRepeat} disabled={repeating}>{repeating ? <LoaderCircle className="spin" size={16} /> : <RefreshCw size={16} />} Repetir corrida</button></section>
        {error && <div className="alert error"><AlertCircle size={18} />{error}</div>}
        <section className="metric-grid"><article className="metric primary-metric"><span>Máxima concentración observada · 1 h</span><strong>{format(result.maximum_1h.concentration_ug_m3, 5)} <small>µg/m³</small></strong><em>Calculada directamente por AERMOD</em></article><article className="metric"><span>Ubicación relativa</span><strong>{format(result.maximum_1h.distance_m, 0)} <small>m</small></strong><em>Rumbo {format(result.maximum_1h.bearing_deg, 0)}° desde la fuente</em></article><article className="metric time-metric"><span>Hora final local</span><strong>{hourEnding}</strong><em>AERMOD {result.maximum_1h.aermod_timestamp}</em></article><article className="metric quality"><span>Control del modelo</span><strong><ShieldCheck size={22} /> Aprobado</strong><em>Sin errores fatales</em></article></section>
        {condition && <section className="maximum-condition"><header><Wind size={19} /><div><p className="eyebrow">CONDICIÓN METEOROLÓGICA DEL MÁXIMO</p><h2>Observación procesada correspondiente a {hourEnding}</h2></div></header><div><span><b>Viento</b>{format(condition.wind_speed_m_s, 2)} m/s <small>desde {format(condition.wind_direction_deg, 0)}°</small></span><span><b>Temperatura</b>{format(condition.temperature_k, 1)} K <small>{format(condition.temperature_k - 273.15, 1)} °C</small></span><span><b>Régimen de capa límite</b>{condition.boundary_layer_regime}</span><span><b>Flujo sensible</b>{format(condition.surface_heat_flux_w_m2, 1)} W/m²</span><span><b>Velocidad de fricción u*</b>{format(condition.friction_velocity_m_s, 3)} m/s</span><span><b>Velocidad convectiva w*</b>{condition.convective_velocity_m_s == null ? "No disponible" : `${format(condition.convective_velocity_m_s, 3)} m/s`}</span><span><b>Mezcla convectiva</b>{condition.convective_mixing_height_m == null ? "No disponible" : `${format(condition.convective_mixing_height_m, 0)} m`}</span><span><b>Mezcla mecánica</b>{condition.mechanical_mixing_height_m == null ? "No disponible" : `${format(condition.mechanical_mixing_height_m, 0)} m`}</span><span><b>Longitud Monin–Obukhov</b>{condition.monin_obukhov_length_m == null ? "No disponible" : `${format(condition.monin_obukhov_length_m, 1)} m`}</span><span><b>Humedad relativa</b>{condition.relative_humidity_percent == null ? "No disponible" : `${format(condition.relative_humidity_percent, 0)} %`}</span><span><b>Presión de estación</b>{condition.station_pressure_mb == null ? "No disponible" : `${format(condition.station_pressure_mb, 0)} mb`}</span></div><p>Estos valores provienen de la fila del archivo AERMET `.SFC` usada por AERMOD para la hora del máximo global.</p></section>}
        {hourlyDownwash && !!result.downwash_comparison?.length && <section className="maximum-condition"><header><Factory size={19} /><div><p className="eyebrow">EFECTO DE EDIFICIOS · SERIE HORARIA</p><h2>Comparación directa con la misma corrida sin downwash</h2></div></header><div>{result.downwash_comparison.map((item) => <span key={item.averaging_period}><b>{periodLabel(item.averaging_period)}</b>{format(item.with_downwash_ug_m3, 5)} µg/m³ <small>sin PRIME {format(item.without_downwash_ug_m3, 5)} · {item.change_percent != null && item.change_percent > 0 ? "+" : ""}{format(item.change_percent ?? 0, 2)} %</small></span>)}</div><p>Ambas alternativas usan la misma meteorología NOAA/AERMET, terreno y receptores. La única diferencia son los 36 juegos de parámetros PRIME calculados por BPIPPRM.</p></section>}
        <section className="result-card hourly-map-card"><header><div><p className="eyebrow">DISTRIBUCIÓN ESPACIAL</p><h2>Contornos de concentración máxima de 1 hora</h2></div><MapPinned size={19} /></header>{latitude != null && longitude != null && (result.maximum_1h_by_receptor?.length ?? 0) > 0 ? <HourlyContourMap latitude={latitude} longitude={longitude} result={result} directionStep={scenario.definition.receptors.direction_step_deg} sources={multiResult?.source_positions} buildings={singleDefinition?.downwash.buildings} /> : <div className="alert warning"><AlertCircle size={18} /><div><p>{latitude == null || longitude == null ? "Este escenario no tiene coordenadas de fuente. Repetilo informando latitud y longitud para superponer los contornos sobre el mapa." : "Esta corrida es anterior a la incorporación de la superficie espacial. Repetila para generar los contornos."}</p></div></div>}</section>
        <section className="maximum-condition"><header><Clock3 size={19} /><div><p className="eyebrow">COBERTURA METEOROLÓGICA</p><h2>{station} · secuencia cronológica {result.year}</h2></div></header><div><span><b>Horas del período</b>{result.meteorology_total_hours.toLocaleString("es-AR")}</span><span><b>Horas utilizables</b>{result.meteorology_usable_hours.toLocaleString("es-AR")}</span><span><b>Cobertura utilizable</b>{format(result.meteorology_usable_percent, 2)} %</span><span><b>Receptores</b>{result.receptor_count.toLocaleString("es-AR")}</span><span><b>Terreno</b>{result.terrain_mode === "complex" ? `Complejo · AERMAP${multiResult ? ` · ${multiResult.source_count} cotas de fuente` : isHourlyResult(result) && result.source_elevation_m != null ? ` · fuente ${format(result.source_elevation_m, 1)} m` : ""}` : "Plano"}</span><span><b>Downwash</b>{hourlyDownwash ? "BPIPPRM 04274 · PRIME" : "No incluido"}</span></div><p>Los faltantes y las calmas permanecen tal como fueron informados y procesados por AERMET. No se aplican sustituciones horarias ni factores empíricos de screening.</p></section>
        <section className="result-layout lower"><article className="result-card periods-card"><header><div><p className="eyebrow">PERÍODOS DE PROMEDIO</p><h2>Máximos calculados directamente</h2></div></header><div className="period-list">{directPeriods.map((period) => <div key={period.averaging_period}><span>{periodLabel(period.averaging_period)}<small>AERMOD cronológico{hourlyDownwash ? " + PRIME" : ""}</small></span><div className="bar-track"><i style={{ width: `${directMaximum ? period.concentration_ug_m3 / directMaximum * 100 : 0}%` }} /></div><strong>{format(period.concentration_ug_m3, 5)} <small>µg/m³</small></strong>{period.hour_ending_local && <em>fin {new Date(period.hour_ending_local).toLocaleString("es-AR", { timeZone: "America/Argentina/Buenos_Aires", dateStyle: "short", timeStyle: "short" })}</em>}</div>)}</div><p className="method-note">Los cinco valores provienen de promedios nativos de AERMOD sobre la serie horaria. No se aplican factores de escalado de AERSCREEN.</p></article><article className="result-card trace-card"><header><div><p className="eyebrow">TRAZABILIDAD</p><h2>Información de corrida</h2></div><ShieldCheck size={19} /></header><div className="trace-list"><span><b>Modalidad</b>Horario observado</span><span><b>Meteorología</b>NOAA ISD + IGRA<small>Procesada con AERMET 26135</small></span><span><b>Versión</b>AERMOD 26135{hourlyDownwash ? " · BPIPPRM 04274" : ""}</span><span><b>Duración</b>{duration(run)}</span><span><b>Estado AERMOD</b>{result.aermod_finished_successfully ? "Finalización correcta" : "Error"}</span><span><b>ID de corrida</b><code>{run.id}</code></span></div></article></section>
        <section className="result-card artifacts-card"><header><div><p className="eyebrow">ARCHIVOS DE AUDITORÍA</p><h2>Entradas, meteorología, resultados y registros</h2></div><span>{artifacts.length} archivos</span></header><div className="artifact-table">{artifacts.filter((artifact) => artifact.kind !== "executable").map((artifact) => <div key={artifact.id}><FileCode2 size={17} /><span><b>{artifact.name}</b><small>{artifact.kind} · {(artifact.size_bytes / 1024).toFixed(1)} KB · SHA-256 {artifact.sha256.slice(0, 12)}…</small></span><a href={api.artifactUrl(run.id, artifact.id)}><Download size={16} /> Descargar</a></div>)}</div></section>
      </main>
    </div>
  );
}

export default function ResultsView({ initialRun, scenario, onBack, onRunChanged, onCredentials }: { initialRun: Run; scenario: Scenario; onBack: () => void; onRunChanged: (run: Run) => void; onCredentials: () => void }) {
  const [run, setRun] = useState(initialRun);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [error, setError] = useState("");
  const [repeating, setRepeating] = useState(false);
  const [sectorsOpen, setSectorsOpen] = useState(false);
  const chartExportRef = useRef<HTMLDivElement>(null);
  const mapExportRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setRun(initialRun); }, [initialRun]);
  useEffect(() => {
    if (run.status === "completed" || run.status === "failed") return;
    const timer = window.setInterval(async () => {
      try {
        const current = await api.getRun(run.id);
        setRun(current);
        onRunChanged(current);
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "No se pudo consultar la corrida.");
      }
    }, 600);
    return () => window.clearInterval(timer);
  }, [run.id, run.status, onRunChanged]);

  useEffect(() => {
    if (run.status !== "completed") return;
    void api.listArtifacts(run.id).then(setArtifacts).catch((reason) => setError(reason instanceof Error ? reason.message : "No se pudieron listar los archivos."));
  }, [run.id, run.status]);

  const periods = useMemo(() => run.result && !isHourlyResult(run.result) && !isMultiSourceHourlyResult(run.result) ? [
    ["1 hora", run.result.maximum_1h_ug_m3, "Calculado"],
    ["3 horas", run.result.scaled_3h_ug_m3, "× 1,00"],
    ["8 horas", run.result.scaled_8h_ug_m3, "× 0,90"],
    ["24 horas", run.result.scaled_24h_ug_m3, "× 0,60"],
    ["Anual", run.result.scaled_annual_ug_m3, "× 0,10"],
  ] as const : [], [run.result]);

  const repeat = async () => {
    setRepeating(true); setError("");
    try {
      const repeated = await api.repeatRun(run.id);
      setArtifacts([]); setRun(repeated); onRunChanged(repeated);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo repetir la corrida."); }
    finally { setRepeating(false); }
  };

  const exportPng = async (node: HTMLDivElement | null, suffix: string) => {
    if (!node) return;
    setError("");
    try {
      const dataUrl = await toPng(node, {
        backgroundColor: "#ffffff",
        cacheBust: true,
        pixelRatio: 2,
        filter: (element) => !(element instanceof HTMLElement && element.hasAttribute("data-export-ignore")),
      });
      const link = document.createElement("a");
      const safeName = scenario.name.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-zA-Z0-9_-]+/g, "-").replace(/^-|-$/g, "").toLowerCase() || "aermod";
      link.download = `${safeName}-${suffix}.png`;
      link.href = dataUrl;
      link.click();
    } catch {
      setError("No se pudo generar el PNG. Alguna capa remota del mapa puede estar bloqueando la captura; probá ocultarla y volvé a exportar.");
    }
  };

  if (run.status === "pending" || run.status === "running") {
    const total = run.progress_total || 1;
    const current = run.progress_current || 0;
    const percent = run.status === "pending" ? 0 : Math.min(100, Math.round(current / total * 100));
    const hourly = isHourlyDefinition(scenario.definition) || isMultiSourceHourlyDefinition(scenario.definition);
    return <div className="results-shell"><header className="topbar"><button className="back-dashboard" onClick={onBack}><ArrowLeft size={18} /> Escenarios</button><div className="brand-center">{hourly ? <Clock3 size={20} /> : <Wind size={20} />} AERMOD {hourly ? "Horario" : "Screening"}</div><button className="credentials-button wizard-credentials" onClick={onCredentials}><KeyRound size={15} /> Credenciales</button></header><main className="run-progress"><div className="progress-orbit"><LoaderCircle className="spin" size={36} /></div><p className="eyebrow">CORRIDA {run.status === "pending" ? "EN COLA" : "EN PROCESO"}</p><h1>{hourly ? "Procesando la secuencia horaria" : "Calculando el peor caso"}</h1><p>{hourly ? "AERMOD evalúa la meteorología NOAA/AERMET 2024 sobre la red omnidireccional." : "MAKEMET genera la matriz meteorológica y AERMOD evalúa los receptores."} Esta vista se actualizará automáticamente.</p><div className="run-progress-meter" aria-label={`Progreso ${percent}%`}><div><i style={{ width: `${percent}%` }} /></div><span><strong>{percent}%</strong>{run.progress_total > 1 ? `${current} de ${run.progress_total} ejecuciones` : run.status === "pending" ? "Esperando inicio" : "Ejecutando"}</span><p>{run.progress_label || (run.status === "pending" ? "Corrida en cola" : "Preparando el modelo")}</p></div><div className="progress-steps"><span className="done"><CheckCircle2 /> Datos validados</span><span className="active"><LoaderCircle className="spin" /> Ejecutando modelo</span><span><Gauge /> Procesando resultados</span></div><code>{run.id}</code></main></div>;
  }

  if (run.status === "failed" || !run.result) {
    return <div className="results-shell"><header className="topbar"><button className="back-dashboard" onClick={onBack}><ArrowLeft size={18} /> Escenarios</button><button className="credentials-button wizard-credentials" onClick={onCredentials}><KeyRound size={15} /> Credenciales</button></header><main className="run-progress failed"><AlertCircle size={44} /><h1>La corrida no pudo completarse</h1><p>{run.error || "Revisá los artefactos y la configuración del motor."}</p><button className="secondary" onClick={onBack}>Volver</button></main></div>;
  }

  const result = run.result;
  if (isHourlyResult(result) && isHourlyDefinition(scenario.definition)) {
    return <HourlyCompleted run={run} scenario={scenario as Scenario & { definition: HourlyScenarioDefinition }} result={result} artifacts={artifacts} error={error} repeating={repeating} onBack={onBack} onCredentials={onCredentials} onRepeat={() => void repeat()} />;
  }
  if (isMultiSourceHourlyResult(result) && isMultiSourceHourlyDefinition(scenario.definition)) {
    return <HourlyCompleted run={run} scenario={scenario as Scenario & { definition: MultiSourceHourlyScenarioDefinition }} result={result} artifacts={artifacts} error={error} repeating={repeating} onBack={onBack} onCredentials={onCredentials} onRepeat={() => void repeat()} />;
  }
  if (isHourlyResult(result) || isHourlyDefinition(scenario.definition) || isMultiSourceHourlyResult(result) || isMultiSourceHourlyDefinition(scenario.definition)) {
    return <div className="results-shell"><main className="run-progress failed"><AlertCircle size={44} /><h1>Resultado incompatible</h1><p>La modalidad del escenario y del resultado no coinciden.</p><button className="secondary" onClick={onBack}>Volver</button></main></div>;
  }
  const sectors = result.sector_results ?? [];
  const condition = result.maximum_condition;
  const maximumSectors = result.maximum_sectors_deg ?? sectors.filter((sector) => Math.abs(sector.maximum_1h_ug_m3 - result.maximum_1h_ug_m3) <= Math.max(1e-8, result.maximum_1h_ug_m3 * 1e-6)).map((sector) => sector.wind_direction_deg);
  const maximumImpacts: MaximumImpact[] = maximumSectors.map((windDirectionDeg) => {
    const sector = sectors.find((item) => item.wind_direction_deg === windDirectionDeg);
    return {
      windDirectionDeg,
      distanceM: sector?.maximum_distance_m ?? result.maximum_distance_m,
      concentration: sector?.maximum_1h_ug_m3 ?? result.maximum_1h_ug_m3,
    };
  });
  const latitude = scenario.definition.source.latitude_deg;
  const longitude = scenario.definition.source.longitude_deg;
  const hasCoordinates = latitude != null && longitude != null;
  return (
    <div className="results-shell">
      <header className="topbar"><button className="back-dashboard" onClick={onBack}><ArrowLeft size={18} /> Escenarios</button><div className="brand-center"><Wind size={20} /> AERMOD Screening</div><button className="credentials-button wizard-credentials" onClick={onCredentials}><KeyRound size={15} /> Credenciales</button><span className="completed-label"><CheckCircle2 size={14} /> COMPLETADA</span></header>
      <main className="results-main">
        <section className="results-heading"><div><p className="eyebrow">RESULTADOS DE SCREENING</p><h1>{scenario.name}</h1><p>{scenario.definition.source.source_id} · {scenario.definition.pollutant_id} · {scenario.definition.dispersion_mode === "rural" ? "Rural" : "Urbano"}</p></div><button className="secondary" onClick={() => void repeat()} disabled={repeating}>{repeating ? <LoaderCircle className="spin" size={16} /> : <RefreshCw size={16} />} Repetir corrida</button></section>
        {error && <div className="alert error"><AlertCircle size={18} />{error}</div>}
        <section className="metric-grid"><article className="metric primary-metric"><span>Máxima concentración · 1 h</span><strong>{format(result.maximum_1h_ug_m3, 5)} <small>µg/m³</small></strong><em>{condition ? `${condition.wind_speed_m_s.toFixed(2)} m/s · ${condition.stability}` : "Peor condición evaluada"}</em></article><article className="metric"><span>Distancia del máximo</span><strong>{format(result.maximum_distance_m, 0)} <small>m</small></strong><em>{maximumSectors.length > 1 ? `${maximumSectors.length} sectores empatados` : result.maximum_direction_deg != null ? `Viento desde ${format(result.maximum_direction_deg, 0)}°` : "Desde la fuente"}</em></article><article className="metric"><span>Distancias evaluadas</span><strong>{result.concentration_by_distance.length}</strong>{sectors.length > 0 ? <button className="sector-link" onClick={() => setSectorsOpen(true)}><Table2 size={14} /> Ver {sectors.length} sectores</button> : <em>Curva concentración-distancia</em>}</article><article className="metric quality"><span>Control de calidad</span><strong><ShieldCheck size={22} /> Aprobado</strong><em>Sin errores fatales</em></article></section>
        {condition && <section className="maximum-condition"><header><Wind size={19} /><div><p className="eyebrow">CONDICIÓN DETERMINANTE</p><h2>{maximumSectors.length > 1 ? `${maximumSectors.length} sectores empatan en la máxima concentración` : "Condición sintética que produjo la máxima concentración"}</h2></div></header><div><span><b>Dirección del viento</b>{maximumSectors.length > 1 ? "No única" : `${format(condition.wind_direction_deg, 0)}°`} <small>{maximumSectors.length > 1 ? "ver tabla sectorial" : "desde donde sopla"}</small></span><span><b>Velocidad</b>{format(condition.wind_speed_m_s, 2)} m/s</span><span><b>Temperatura</b>{format(condition.temperature_k, 1)} K</span><span><b>Régimen</b>{condition.stability}</span><span><b>u*</b>{format(condition.friction_velocity_m_s, 3)} m/s</span><span><b>Altura de mezcla convectiva</b>{condition.mixing_height_m != null && condition.mixing_height_m > 0 ? format(condition.mixing_height_m, 0) + " m" : "No aplicable"}</span></div><p>La fecha {condition.synthetic_date} es un identificador de la matriz sintética de MAKEMET; no representa una fecha observada.</p></section>}
        {!!result.roughness_sensitivity?.length && <section className="maximum-condition"><header><Wind size={19} /><div><p className="eyebrow">SENSIBILIDAD DE SUPERFICIE</p><h2>Rugosidad seleccionada por máxima concentración</h2></div></header><div>{result.roughness_sensitivity.map((candidate) => <span key={candidate.roughness_m}><b>z₀ {format(candidate.roughness_m, 4)} m</b>{format(candidate.maximum_1h_ug_m3, 5)} µg/m³ <small>{candidate.roughness_m === result.selected_surface_roughness_m ? "seleccionada" : `a ${format(candidate.maximum_distance_m, 0)} m`}</small></span>)}</div><p>La selección compara hasta cinco valores en los 36 sectores sin downwash. La corrida final usa la rugosidad que produjo el máximo más alto y luego aplica la configuración completa del escenario.</p></section>}
        {result.without_downwash_maximum_1h_ug_m3 != null && <section className="maximum-condition"><header><Factory size={19} /><div><p className="eyebrow">EFECTO DE EDIFICIOS</p><h2>Comparación con la misma corrida sin downwash</h2></div></header><div><span><b>Sin downwash</b>{format(result.without_downwash_maximum_1h_ug_m3, 5)} µg/m³</span><span><b>Con downwash</b>{format(result.maximum_1h_ug_m3, 5)} µg/m³</span><span><b>Diferencia</b>{result.downwash_difference_1h_ug_m3 != null && result.downwash_difference_1h_ug_m3 > 0 ? "+" : ""}{format(result.downwash_difference_1h_ug_m3 ?? 0, 5)} µg/m³</span><span><b>Cambio relativo</b>{result.downwash_change_percent != null && result.downwash_change_percent > 0 ? "+" : ""}{format(result.downwash_change_percent ?? 0, 1)} %</span><span><b>Factor</b>{format(result.downwash_ratio ?? 0, 2)}×</span></div><p>Ambas alternativas usan los mismos 36 sectores, meteorología sintética y receptores. La única diferencia son los parámetros PRIME calculados por BPIPPRM.</p></section>}
        {result.flat_terrain_maximum_1h_ug_m3 != null && <section className="maximum-condition"><header><MapPinned size={19} /><div><p className="eyebrow">EFECTO DEL RELIEVE</p><h2>Comparación terreno plano / terreno complejo</h2></div></header><div><span><b>Terreno plano</b>{format(result.flat_terrain_maximum_1h_ug_m3, 5)} µg/m³ <small>a {format(result.flat_terrain_maximum_distance_m ?? 0, 0)} m{result.flat_terrain_maximum_direction_deg != null ? ` · ${format(result.flat_terrain_maximum_direction_deg, 0)}°` : ""}</small></span><span><b>Terreno complejo</b>{format(result.maximum_1h_ug_m3, 5)} µg/m³ <small>a {format(result.maximum_distance_m, 0)} m{result.maximum_direction_deg != null ? ` · ${format(result.maximum_direction_deg, 0)}°` : ""}</small></span><span><b>Complejo − plano</b>{result.terrain_difference_1h_ug_m3 != null && result.terrain_difference_1h_ug_m3 > 0 ? "+" : ""}{format(result.terrain_difference_1h_ug_m3 ?? 0, 5)} µg/m³</span><span><b>Cambio relativo</b>{result.terrain_change_percent != null && result.terrain_change_percent > 0 ? "+" : ""}{format(result.terrain_change_percent ?? 0, 1)} %</span><span><b>Factor complejo/plano</b>{format(result.complex_to_flat_ratio ?? 0, 2)}×</span></div><p>El control conserva fuente, meteorología, receptores y downwash. Solo reemplaza las elevaciones procesadas por AERMAP por una elevación uniforme, para aislar el efecto del relieve.</p></section>}
        <section className="result-layout"><article className="result-card chart-card"><header><div><p className="eyebrow">PERFIL DE IMPACTO</p><h2>Concentración por distancia</h2></div><button className="visual-export" data-export-ignore onClick={() => void exportPng(chartExportRef.current, "perfil-concentracion")}><Download size={15} /> PNG</button></header><div ref={chartExportRef} className="export-visual"><ConcentrationChart points={result.concentration_by_distance} maximumDistance={result.maximum_distance_m} /></div></article><article className="result-card"><header><div><p className="eyebrow">CONTEXTO ESPACIAL</p><h2>{hasCoordinates ? "Concentraciones sobre mapa" : "Búsqueda radial"}</h2></div><button className="visual-export" data-export-ignore onClick={() => void exportPng(mapExportRef.current, "mapa-concentraciones")}><Download size={15} /> PNG</button></header><div ref={mapExportRef} className="export-visual">{hasCoordinates ? <GeoreferencedMap latitude={latitude} longitude={longitude} points={result.concentration_by_distance} buildings={scenario.definition.downwash?.buildings} maximumImpacts={maximumImpacts} meteorology={scenario.definition.meteorology} /> : <ContextMap distance={result.maximum_distance_m} />}</div></article></section>
        <section className="result-layout lower"><article className="result-card periods-card"><header><div><p className="eyebrow">PERÍODOS DE PROMEDIO</p><h2>Concentraciones escaladas</h2></div></header><div className="period-list">{periods.map(([label, value, factor], index) => <div key={label}><span>{label}<small>{factor}</small></span><div className="bar-track"><i style={{ width: `${(value / result.maximum_1h_ug_m3) * 100}%` }} /></div><strong>{format(value, 5)} <small>µg/m³</small></strong>{index > 0 && <em>Estimado</em>}</div>)}</div><p className="method-note">Solo el valor de 1 hora es calculado directamente. Los demás utilizan los factores fijos de AERSCREEN.</p></article><article className="result-card trace-card"><header><div><p className="eyebrow">TRAZABILIDAD</p><h2>Información de corrida</h2></div><ShieldCheck size={19} /></header><div className="trace-list"><span><b>Versión</b>AERMOD 26135 · MAKEMET 16216{scenario.definition.terrain?.mode === "complex" ? " · AERMAP 24142" : ""}</span><span><b>Terreno</b>{scenario.definition.terrain?.mode === "complex" ? "Complejo · Copernicus GLO-30" : "Plano"}</span>{scenario.definition.meteorology.observations_selection && <span><b>Meteorología observada</b>{scenario.definition.meteorology.observations_selection}<small>{scenario.definition.meteorology.observations_period_start} a {scenario.definition.meteorology.observations_period_end}</small></span>}<span><b>Duración</b>{duration(run)}</span><span><b>Estado AERMOD</b>{result.aermod_finished_successfully ? "Finalización correcta" : "Error"}</span><span><b>Errores fatales</b>{result.no_fatal_errors ? "Ninguno" : "Detectados"}</span><span><b>ID de corrida</b><code>{run.id}</code></span></div></article></section>
        <section className="result-card artifacts-card"><header><div><p className="eyebrow">ARCHIVOS DE AUDITORÍA</p><h2>Entradas, resultados y registros</h2></div><span>{artifacts.length} archivos</span></header><div className="artifact-table">{artifacts.filter((artifact) => artifact.kind !== "executable").map((artifact) => <div key={artifact.id}><FileCode2 size={17} /><span><b>{artifact.name}</b><small>{artifact.kind} · {(artifact.size_bytes / 1024).toFixed(1)} KB · SHA-256 {artifact.sha256.slice(0, 12)}…</small></span><a href={api.artifactUrl(run.id, artifact.id)}><Download size={16} /> Descargar</a></div>)}</div></section>
      </main>
      {sectorsOpen && <div className="map-modal" role="dialog" aria-modal="true" aria-label="Sectores meteorológicos"><div className="sector-modal-panel"><header><div><p className="eyebrow">SCREENING DIRECCIONAL</p><h2>36 sectores meteorológicos de 10°</h2><p>Cada dirección indica de dónde sopla el viento. La pluma se desplaza aproximadamente 180° en sentido opuesto. {maximumSectors.length > 1 && `${maximumSectors.length} sectores empatan en el máximo global.`}</p></div><button onClick={() => setSectorsOpen(false)} aria-label="Cerrar tabla"><X size={22} /></button></header><div className="sector-table"><div className="sector-table-head"><b>Viento desde</b><b>Pluma hacia</b><b>Máximo 1 h</b><b>Distancia</b></div>{sectors.map((sector) => { const winning = maximumSectors.includes(sector.wind_direction_deg); return <div key={sector.wind_direction_deg} className={winning ? "winning-sector" : ""}><span>{format(sector.wind_direction_deg, 0)}°</span><span>{format((sector.wind_direction_deg + 180) % 360, 0)}°</span><strong>{format(sector.maximum_1h_ug_m3, 5)} µg/m³</strong><span>{format(sector.maximum_distance_m, 0)} m</span>{winning && <em>MÁXIMO GLOBAL</em>}</div>; })}</div></div></div>}
    </div>
  );
}
