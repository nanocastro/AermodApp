import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronDown,
  ClipboardCopy,
  Factory,
  FileCheck2,
  FolderPlus,
  Gauge,
  Info,
  KeyRound,
  LoaderCircle,
  Plus,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Wind,
} from "lucide-react";
import { api } from "./api";
import { toHourlyScenarioDefinition, toMultiSourceHourlyScenarioDefinition, toScenarioDefinition, validateStep, warnings } from "./conversions";
import ResultsView from "./ResultsView";
import { localSurfaceHelp } from "./surfacePresentation";
import { EPA_DEFAULTS, isHourlyDefinition, isMultiSourceHourlyDefinition, type CredentialStatus, type Project, type Run, type Scenario, type StationEstimate, type StationStatistics, type SurfaceEstimate, type TerrainPreparation, type WizardData } from "./types";

const STEPS = [
  { label: "Proyecto", icon: FolderPlus },
  { label: "Fuente", icon: Factory },
  { label: "Modelación", icon: Wind },
  { label: "Revisión", icon: FileCheck2 },
];

function numeric(value: string): number {
  return value === "" ? Number.NaN : Number(value);
}

function fromScenario(project: Project, scenario: Scenario): WizardData {
  const definition = scenario.definition;
  const primarySource = isMultiSourceHourlyDefinition(definition) ? definition.sources[0] : definition.source;
  const building = "downwash" in definition ? definition.downwash?.buildings?.[0] : undefined;
  const eastValues = building?.vertices.map((vertex) => vertex.east_m) ?? [];
  const northValues = building?.vertices.map((vertex) => vertex.north_m) ?? [];
  const buildingFields = {
    buildingId: building?.building_id ?? "BUILDING",
    buildingHeight: building?.height_m ?? 20,
    buildingBaseElevation: building?.base_elevation_m ?? 0,
    buildingCenterEast: eastValues.length ? eastValues.reduce((a, b) => a + b, 0) / eastValues.length : 25,
    buildingCenterNorth: northValues.length ? northValues.reduce((a, b) => a + b, 0) / northValues.length : 0,
    buildingLength: eastValues.length ? Math.max(...eastValues) - Math.min(...eastValues) : 40,
    buildingWidth: northValues.length ? Math.max(...northValues) - Math.min(...northValues) : 25,
    buildingRotation: 0,
  };
  const common: WizardData = {
    ...EPA_DEFAULTS,
    projectName: project.name,
    projectDescription: project.description,
    responsible: project.responsible,
    scenarioName: `${scenario.name} - copia`,
    pollutantId: definition.pollutant_id,
    sourceId: primarySource.source_id,
    emissionRate: primarySource.emission_rate_g_s,
    emissionUnit: "g/s",
    stackHeight: primarySource.stack_height_m,
    heightUnit: "m",
    stackTemperature: primarySource.stack_temperature_k,
    temperatureUnit: "K",
    exitVelocity: primarySource.exit_velocity_m_s,
    velocityUnit: "m/s",
    stackDiameter: primarySource.stack_diameter_m,
    diameterUnit: "m",
    latitude: primarySource.latitude_deg ?? Number.NaN,
    longitude: primarySource.longitude_deg ?? Number.NaN,
    dispersionMode: definition.dispersion_mode,
    urbanPopulation: definition.urban_population ?? 100000,
    ambientBoundaryDistance: definition.receptors.ambient_boundary_distance_m,
    searchStart: definition.receptors.search_start_m,
    searchEnd: definition.receptors.search_end_m,
    searchStep: definition.receptors.search_step_m,
    receptorHeight: definition.receptors.receptor_height_m,
  };
  if (isMultiSourceHourlyDefinition(definition)) {
    return {
      ...common,
      runMode: "multi_source_hourly",
      multiSources: definition.sources.map((source) => ({
        sourceId: source.source_id,
        emissionRate: source.emission_rate_g_s,
        stackHeight: source.stack_height_m,
        stackTemperature: source.stack_temperature_k,
        exitVelocity: source.exit_velocity_m_s,
        stackDiameter: source.stack_diameter_m,
        latitude: source.latitude_deg ?? Number.NaN,
        longitude: source.longitude_deg ?? Number.NaN,
      })),
      hourlyStation: definition.meteorology.station,
      hourlyYear: definition.meteorology.year,
      directionStep: definition.receptors.direction_step_deg,
      terrainMode: definition.terrain.mode,
      terrainProvider: definition.terrain.provider ?? "copernicus",
      downwashEnabled: false,
    };
  }
  if (isHourlyDefinition(definition)) {
    return {
      ...common,
      runMode: "hourly",
      hourlyStation: definition.meteorology.station,
      hourlyYear: definition.meteorology.year,
      directionStep: definition.receptors.direction_step_deg,
      terrainMode: definition.terrain.mode,
      terrainProvider: definition.terrain.provider ?? "copernicus",
      downwashEnabled: definition.downwash.enabled,
      ...buildingFields,
    };
  }
  return {
    ...common,
    runMode: "screening",
    minimumWindSpeed: definition.meteorology.minimum_wind_speed_m_s,
    anemometerHeight: definition.meteorology.anemometer_height_m,
    minimumTemperature: definition.meteorology.minimum_temperature_k,
    maximumTemperature: definition.meteorology.maximum_temperature_k,
    albedo: definition.meteorology.albedo,
    bowenRatio: definition.meteorology.bowen_ratio,
    surfaceRoughness: definition.meteorology.surface_roughness_m,
    roughnessCandidates: definition.meteorology.roughness_candidates_m ?? [],
    windDirection: definition.meteorology.wind_direction_deg,
    adjustFrictionVelocity: definition.meteorology.adjust_friction_velocity,
    observationsSource: definition.meteorology.observations_source ?? null,
    observationsPeriodStart: definition.meteorology.observations_period_start ?? null,
    observationsPeriodEnd: definition.meteorology.observations_period_end ?? null,
    observationsSelection: definition.meteorology.observations_selection ?? null,
    baseElevation: definition.receptors.base_elevation_m,
    terrainMode: definition.terrain?.mode ?? "flat",
    terrainProvider: definition.terrain?.provider ?? "copernicus",
    compareTerrainWithFlat: definition.terrain?.compare_with_flat ?? false,
    downwashEnabled: definition.downwash?.enabled ?? false,
    ...buildingFields,
    buildingBaseElevation: building?.base_elevation_m ?? definition.receptors.base_elevation_m,
  };
}

type FieldProps = {
  label: string;
  value: string | number;
  onChange: (value: string) => void;
  type?: "text" | "number";
  help?: string;
  min?: number;
  step?: number;
  unit?: React.ReactNode;
};

const PARAMETER_HELP: Record<string, string> = {
  "Nombre del proyecto": "Nombre administrativo que agrupa escenarios y corridas relacionadas.",
  Responsable: "Persona o equipo responsable de preparar y revisar el estudio.",
  "Nombre del escenario": "Identifica una combinación inmutable de fuente, superficie, meteorología y receptores.",
  "ID de fuente": "Código corto usado por AERMOD para identificar la fuente emisora.",
  Contaminante: "Identificador del compuesto evaluado; debe ser coherente con la tasa de emisión ingresada.",
  Latitud: "Coordenada geográfica WGS84 de la chimenea. Permite ubicar resultados y solicitar terreno/cobertura del suelo.",
  Longitud: "Coordenada geográfica WGS84 de la chimenea. En Argentina normalmente será negativa.",
  "Tasa de emisión": "Masa de contaminante emitida por unidad de tiempo. En screening la concentración escala linealmente con este valor.",
  "Altura de chimenea": "Altura física de la boca de la chimenea respecto del terreno en su base.",
  "Temperatura de salida": "Temperatura del gas en la boca; interviene en la flotabilidad de la pluma.",
  "Velocidad de salida": "Velocidad vertical del gas al abandonar la chimenea; afecta el ascenso de la pluma.",
  "Diámetro interior": "Diámetro interno de la boca circular de la chimenea.",
  "Población urbana": "Población usada por AERMOD para parametrizar la dispersión en modo urbano.",
  Albedo: "Fracción de radiación solar reflejada por la superficie (0–1). Afecta el balance energético y la turbulencia convectiva.",
  "Razón de Bowen": "Relación entre flujo de calor sensible y latente; representa la humedad efectiva de la superficie.",
  Rugosidad: "Longitud de rugosidad aerodinámica z₀. Representa el efecto de vegetación, edificios y otros obstáculos sobre el viento.",
  "Temperatura mínima": "Extremo inferior de temperatura ambiente usado por MAKEMET para construir condiciones de screening.",
  "Temperatura máxima": "Extremo superior de temperatura ambiente usado por MAKEMET.",
  "Viento mínimo": "Menor velocidad de viento evaluada por la matriz meteorológica sintética.",
  "Altura anemómetro": "Altura sobre el terreno a la que se representa la medición del viento.",
  Dirección: "Dirección meteorológica del viento, medida desde el norte. En búsqueda radial no representa una cronología real.",
  "Límite ambiental": "Distancia desde la fuente al límite de acceso público o inicio de receptores discretos.",
  "Inicio búsqueda": "Primera distancia de la grilla fina usada para localizar el máximo.",
  "Fin búsqueda": "Última distancia de la grilla fina usada para localizar el máximo.",
  Paso: "Separación entre receptores sucesivos de la grilla fina.",
  "Elevación base": "Elevación común del terreno en el caso plano; no sustituye el procesamiento AERMAP.",
  "Altura receptor": "Altura del punto de evaluación sobre el terreno local.",
  "ID de edificio": "Código corto usado por BPIPPRM y AERMOD para identificar el obstáculo.",
  "Altura del edificio": "Altura del techo sobre la base; controla la región de influencia aerodinámica.",
  "Centro Este": "Desplazamiento del centro respecto de la chimenea; este es positivo.",
  "Centro Norte": "Desplazamiento del centro respecto de la chimenea; norte es positivo.",
  Largo: "Dimensión principal de la planta rectangular.",
  Ancho: "Dimensión transversal de la planta rectangular.",
  Rotación: "Giro horario de la planta respecto del eje Este.",
};

function Field({ label, value, onChange, type = "text", help, min, step, unit }: FieldProps) {
  const explanation = PARAMETER_HELP[label];
  return (
    <label className="field">
      <span className="field-label">{label}{explanation && <span className="help-tip" tabIndex={0} aria-label={`Ayuda: ${label}`}><Info size={13} /><span role="tooltip">{explanation}</span></span>}</span>
      <span className="input-wrap">
        <input
          type={type}
          value={Number.isNaN(value) ? "" : value}
          onChange={(event) => onChange(event.target.value)}
          min={min}
          step={step}
        />
        {unit}
      </span>
      {help && <small>{help}</small>}
    </label>
  );
}

function UnitSelect({ value, options, onChange }: { value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <span className="unit-select">
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => <option key={option}>{option}</option>)}
      </select>
      <ChevronDown size={14} />
    </span>
  );
}

function SummaryRow({ label, value, unit }: { label: string; value: string | number; unit?: string }) {
  return (
    <div className="summary-row">
      <span>{label}</span>
      <strong>{value}{unit && <em> {unit}</em>}</strong>
    </div>
  );
}

function BuildingPreview({ data }: { data: WizardData }) {
  const building = toScenarioDefinition(data).downwash.buildings[0];
  if (!building) return null;
  const width = 520;
  const height = 330;
  const centerX = width / 2;
  const centerY = height / 2;
  const extent = Math.max(20, ...building.vertices.flatMap((vertex) => [Math.abs(vertex.east_m), Math.abs(vertex.north_m)]), Math.abs(data.buildingCenterEast), Math.abs(data.buildingCenterNorth));
  const scale = Math.min((width - 100) / (2 * extent), (height - 80) / (2 * extent));
  const point = (east: number, north: number) => `${centerX + east * scale},${centerY - north * scale}`;
  const gridStep = extent <= 50 ? 10 : extent <= 150 ? 25 : 50;
  const gridLines = Array.from({ length: Math.floor(extent / gridStep) }, (_, index) => (index + 1) * gridStep);
  return (
    <figure className="building-preview">
      <figcaption><div><strong>Vista en planta</strong><span>Geometría respecto de la chimenea</span></div><small>Escala automática · cuadrícula {gridStep} m</small></figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Planta del edificio respecto de la chimenea">
        <rect width={width} height={height} rx="10" className="building-preview-bg" />
        {gridLines.flatMap((offset) => [offset, -offset]).map((offset) => <g key={offset}><line x1={centerX + offset * scale} y1="20" x2={centerX + offset * scale} y2={height - 20} className="building-grid" /><line x1="20" y1={centerY - offset * scale} x2={width - 20} y2={centerY - offset * scale} className="building-grid" /></g>)}
        <line x1="20" y1={centerY} x2={width - 20} y2={centerY} className="building-axis" />
        <line x1={centerX} y1={height - 20} x2={centerX} y2="20" className="building-axis" />
        <text x={width - 29} y={centerY - 8} className="axis-label">E</text><text x={centerX + 9} y="34" className="axis-label">N</text>
        <line x1={centerX} y1={centerY} x2={centerX + data.buildingCenterEast * scale} y2={centerY - data.buildingCenterNorth * scale} className="building-offset" />
        <polygon points={building.vertices.map((vertex) => point(vertex.east_m, vertex.north_m)).join(" ")} className="building-shape" />
        <circle cx={centerX + data.buildingCenterEast * scale} cy={centerY - data.buildingCenterNorth * scale} r="4" className="building-center" />
        <circle cx={centerX} cy={centerY} r="8" className="stack-symbol" /><circle cx={centerX} cy={centerY} r="14" className="stack-ring" />
        <text x={centerX + 17} y={centerY + 21} className="stack-label">CHIMENEA (0, 0)</text>
        <text x={centerX + data.buildingCenterEast * scale + 8} y={centerY - data.buildingCenterNorth * scale - 9} className="building-label">{building.building_id} · {building.height_m} m</text>
      </svg>
      <div className="building-preview-values"><span>Centro: E {data.buildingCenterEast} m · N {data.buildingCenterNorth} m</span><span>Planta: {data.buildingLength} × {data.buildingWidth} m · giro {data.buildingRotation}°</span></div>
    </figure>
  );
}

type CredentialForm = {
  earthdata_username: string;
  earthdata_password: string;
  cdsapi_key: string;
};

function CredentialsDialog({
  open,
  status,
  form,
  saving,
  onFormChange,
  onClose,
  onSave,
}: {
  open: boolean;
  status: CredentialStatus | null;
  form: CredentialForm;
  saving: boolean;
  onFormChange: (form: CredentialForm) => void;
  onClose: () => void;
  onSave: () => void;
}) {
  if (!open) return null;
  return (
    <div className="credentials-modal" role="dialog" aria-modal="true" aria-label="Configuración de credenciales">
      <section className="credentials-panel">
        <header><div className="credential-icon"><KeyRound size={24} /></div><div><p className="eyebrow">CONFIGURACIÓN LOCAL</p><h2>Acceso a datos ambientales</h2><p>Iniciá sesión en cada proveedor, obtené tus credenciales y pegalas aquí. La aplicación nunca vuelve a mostrarlas.</p></div></header>
        <div className="credential-provider"><div><strong>NASA Earthdata</strong><span>Necesario para descargar albedo MODIS mediante AppEEARS.</span><a href="https://urs.earthdata.nasa.gov/users" target="_blank" rel="noreferrer">Iniciar sesión o crear cuenta ↗</a></div><em className={status?.earthdata_configured ? "configured" : "pending"}>{status?.earthdata_configured ? "CONFIGURADO" : "PENDIENTE"}</em></div>
        <div className="credential-fields"><label><span>Usuario Earthdata</span><input placeholder={status?.earthdata_configured ? "Dejar vacío para conservar" : "Usuario"} value={form.earthdata_username} onChange={(event) => onFormChange({ ...form, earthdata_username: event.target.value })} autoComplete="username" /></label><label><span>Contraseña Earthdata</span><input placeholder={status?.earthdata_configured ? "Dejar vacío para conservar" : "Contraseña"} type="password" value={form.earthdata_password} onChange={(event) => onFormChange({ ...form, earthdata_password: event.target.value })} autoComplete="current-password" /></label></div>
        <div className="credential-provider"><div><strong>Copernicus Climate Data Store</strong><span>Necesario para descargar los flujos ERA5-Land.</span><a href="https://cds.climate.copernicus.eu/how-to-api" target="_blank" rel="noreferrer">Iniciar sesión y copiar el Personal Access Token ↗</a></div><em className={status?.cds_configured ? "configured" : "pending"}>{status?.cds_configured ? "CONFIGURADO" : "PENDIENTE"}</em></div>
        <div className="credential-fields single"><label><span>Personal Access Token de CDS</span><input placeholder={status?.cds_configured ? "Dejar vacío para conservar" : "Token personal"} type="password" value={form.cdsapi_key} onChange={(event) => onFormChange({ ...form, cdsapi_key: event.target.value })} autoComplete="off" /></label></div>
        <div className="credential-security"><ShieldCheck size={18} /><span>En Windows se guardan en Credential Manager, dentro del perfil del usuario. No se incluyen en proyectos, resultados ni archivos exportados.</span></div>
        <footer><button className="secondary" onClick={onClose}>Cerrar</button><button className="primary" disabled={saving || (!form.cdsapi_key && !form.earthdata_username) || Boolean(form.earthdata_username) !== Boolean(form.earthdata_password)} onClick={onSave}>{saving ? <LoaderCircle className="spin" size={16} /> : <KeyRound size={16} />} Guardar credenciales</button></footer>
      </section>
    </div>
  );
}

export default function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [scenarios, setScenarios] = useState<Record<string, Scenario[]>>({});
  const [runs, setRuns] = useState<Record<string, Run[]>>({});
  const [dashboardLoading, setDashboardLoading] = useState(true);
  const [apiError, setApiError] = useState("");
  const [wizardOpen, setWizardOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [data, setData] = useState<WizardData>({ ...EPA_DEFAULTS });
  const [existingProjectId, setExistingProjectId] = useState<string | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [savedScenario, setSavedScenario] = useState<Scenario | null>(null);
  const [activeResult, setActiveResult] = useState<{ scenario: Scenario; run: Run } | null>(null);
  const [terrainPreparation, setTerrainPreparation] = useState<TerrainPreparation | null>(null);
  const [preparingTerrain, setPreparingTerrain] = useState(false);
  const [launchingScenarioId, setLaunchingScenarioId] = useState<string | null>(null);
  const [estimatingSurface, setEstimatingSurface] = useState(false);
  const [surfaceEstimate, setSurfaceEstimate] = useState<SurfaceEstimate | null>(null);
  const [stationEstimate, setStationEstimate] = useState<StationEstimate | null>(null);
  const [stationSelection, setStationSelection] = useState("combined");
  const [estimatingStations, setEstimatingStations] = useState(false);
  const [surfaceProgress, setSurfaceProgress] = useState("");
  const [stationProgress, setStationProgress] = useState("");
  const [credentialStatus, setCredentialStatus] = useState<CredentialStatus | null>(null);
  const [credentialsOpen, setCredentialsOpen] = useState(false);
  const [savingCredentials, setSavingCredentials] = useState(false);
  const [credentialForm, setCredentialForm] = useState({ earthdata_username: "", earthdata_password: "", cdsapi_key: "" });

  const screeningDefinition = useMemo(() => toScenarioDefinition(data), [data]);
  const definition = useMemo(
    () => data.runMode === "hourly" ? toHourlyScenarioDefinition(data) : data.runMode === "multi_source_hourly" ? toMultiSourceHourlyScenarioDefinition(data) : screeningDefinition,
    [data, screeningDefinition],
  );
  const notices = useMemo(() => warnings(data), [data]);
  const surfaceHelp = surfaceEstimate?.meets_minimum_coverage ? localSurfaceHelp(surfaceEstimate) : null;

  const update = <K extends keyof WizardData>(key: K, value: WizardData[K]) => {
    if (["latitude", "longitude", "albedo", "bowenRatio", "surfaceRoughness"].includes(key)) {
      setSurfaceEstimate(null);
    }
    if (["latitude", "longitude", "minimumTemperature", "maximumTemperature", "minimumWindSpeed"].includes(key)) {
      setStationEstimate(null);
    }
    setData((current) => ({
      ...current,
      [key]: value,
      ...(key === "surfaceRoughness" ? { roughnessCandidates: [] } : {}),
      ...(["minimumTemperature", "maximumTemperature", "minimumWindSpeed"].includes(key) ? {
        observationsSource: null,
        observationsPeriodStart: null,
        observationsPeriodEnd: null,
        observationsSelection: null,
      } : {}),
    }));
  };

  const updateMultiSource = (index: number, key: keyof WizardData["multiSources"][number], value: string | number) => {
    setData((current) => ({
      ...current,
      multiSources: current.multiSources.map((source, sourceIndex) => sourceIndex === index ? { ...source, [key]: value } : source),
    }));
  };

  const selectRunMode = (runMode: WizardData["runMode"]) => {
    setData((current) => ({
      ...current,
      runMode,
      ...(runMode !== "screening" ? {
        ambientBoundaryDistance: 100,
        searchStart: 200,
        searchEnd: 5000,
        searchStep: 100,
        directionStep: 10,
        terrainMode: "flat" as const,
        compareTerrainWithFlat: false,
        downwashEnabled: false,
      } : {
        ambientBoundaryDistance: EPA_DEFAULTS.ambientBoundaryDistance,
        searchStart: EPA_DEFAULTS.searchStart,
        searchEnd: EPA_DEFAULTS.searchEnd,
        searchStep: EPA_DEFAULTS.searchStep,
      }),
    }));
  };

  const loadProjects = async () => {
    setDashboardLoading(true);
    setApiError("");
    try {
      setProjects(await api.listProjects());
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "No se pudo conectar con la API.");
    } finally {
      setDashboardLoading(false);
    }
  };

  useEffect(() => {
    void loadProjects();
    void api.credentialStatus().then((status) => {
      setCredentialStatus(status);
      if (!status.earthdata_configured || !status.cds_configured) setCredentialsOpen(true);
    }).catch(() => undefined);
  }, []);

  const saveCredentials = async () => {
    setSavingCredentials(true);
    setApiError("");
    try {
      const status = await api.saveCredentials(credentialForm);
      setCredentialStatus(status);
      setCredentialForm({ earthdata_username: "", earthdata_password: "", cdsapi_key: "" });
      setCredentialsOpen(false);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "No se pudieron guardar las credenciales.");
    } finally {
      setSavingCredentials(false);
    }
  };

  const loadScenarios = async (projectId: string) => {
    try {
      const loaded = await api.listScenarios(projectId);
      setScenarios((current) => ({ ...current, [projectId]: loaded }));
      const runEntries = await Promise.all(
        loaded.map(async (scenario) => [scenario.id, await api.listRuns(scenario.id)] as const),
      );
      setRuns((current) => ({ ...current, ...Object.fromEntries(runEntries) }));
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "No se pudieron cargar los escenarios.");
    }
  };

  const executeScenario = async (scenario: Scenario) => {
    setApiError("");
    setLaunchingScenarioId(scenario.id);
    try {
      if ("terrain" in scenario.definition && scenario.definition.terrain.mode === "complex") {
        setPreparingTerrain(true);
        setTerrainPreparation(await api.prepareTerrain(scenario.id));
      }
      const run = await api.createRun(scenario.id);
      setRuns((current) => ({ ...current, [scenario.id]: [run, ...(current[scenario.id] ?? [])] }));
      setActiveResult({ scenario, run });
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "No se pudo iniciar la corrida.");
    } finally {
      setPreparingTerrain(false);
      setLaunchingScenarioId(null);
    }
  };

  const updateActiveRun = (updated: Run) => {
    if (!activeResult) return;
    setActiveResult({ ...activeResult, run: updated });
    setRuns((current) => ({
      ...current,
      [updated.scenario_id]: [updated, ...(current[updated.scenario_id] ?? []).filter((item) => item.id !== updated.id)],
    }));
  };

  const startNew = () => {
    setData({ ...EPA_DEFAULTS, projectName: "", projectDescription: "", scenarioName: "" });
    setExistingProjectId(null);
    setSavedScenario(null);
    setSurfaceEstimate(null);
    setStationEstimate(null);
    setErrors([]);
    setStep(0);
    setWizardOpen(true);
  };

  const startClone = (project: Project, scenario: Scenario) => {
    setData(fromScenario(project, scenario));
    setExistingProjectId(project.id);
    setSavedScenario(null);
    setSurfaceEstimate(null);
    setStationEstimate(null);
    setErrors([]);
    setStep(0);
    setWizardOpen(true);
  };

  const next = () => {
    const validation = validateStep(step, data);
    setErrors(validation);
    if (!validation.length) setStep((current) => Math.min(3, current + 1));
  };

  const estimateSurface = async () => {
    if (!Number.isFinite(data.latitude) || !Number.isFinite(data.longitude)) {
      setApiError("Ingresá latitud y longitud válidas en la etapa Fuente.");
      return;
    }
    setEstimatingSurface(true);
    setSurfaceProgress("Creando trabajo ambiental");
    setApiError("");
    try {
      let job = await api.createEnvironmentJob("surface", data.latitude, data.longitude);
      while (job.status === "pending" || job.status === "running") {
        setSurfaceProgress(job.progress_label || "Esperando inicio");
        await new Promise((resolve) => window.setTimeout(resolve, 500));
        job = await api.getEnvironmentJob(job.id);
      }
      if (job.status === "failed" || !job.result) {
        const stage = job.progress_label ? `${job.progress_label}: ` : "";
        throw new Error(`${stage}${job.error || "La estimación ambiental falló."}`);
      }
      const estimate = job.result as unknown as SurfaceEstimate;
      setSurfaceEstimate(estimate);
      if (estimate.meets_minimum_coverage) {
        setData((current) => ({ ...current,
          albedo: Number(estimate.albedo.toFixed(3)),
          bowenRatio: Number(estimate.bowen_ratio.toFixed(3)),
          surfaceRoughness: Number(estimate.surface_roughness_m.toFixed(4)),
          roughnessCandidates: [...new Set(estimate.roughness_candidates_m.map((value) => Number(value.toFixed(4))))].sort((left, right) => left - right),
        }));
      } else {
        setApiError(`Los valores locales no se aplicaron porque la cobertura debe superar el ${estimate.minimum_coverage_percent.toFixed(0)} %.`);
      }
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "No se pudieron estimar los parámetros locales.");
    } finally {
      setEstimatingSurface(false);
      setSurfaceProgress("");
    }
  };

  const applyStationStatistics = (statistics: StationStatistics, selection: string, estimate: StationEstimate) => {
    setData((current) => ({
      ...current,
      minimumTemperature: Number((statistics.temperature_min_c + 273.15).toFixed(2)),
      maximumTemperature: Number((statistics.temperature_max_c + 273.15).toFixed(2)),
      minimumWindSpeed: Number(statistics.makemet_minimum_wind_m_s.toFixed(2)),
      observationsSource: estimate.source,
      observationsPeriodStart: estimate.period_start,
      observationsPeriodEnd: estimate.period_end,
      observationsSelection: selection,
    }));
  };

  const estimateStations = async () => {
    if (!Number.isFinite(data.latitude) || !Number.isFinite(data.longitude)) {
      setApiError("Ingresá latitud y longitud válidas en la etapa Fuente.");
      return;
    }
    setEstimatingStations(true);
    setStationProgress("Creando trabajo SMN");
    setApiError("");
    try {
      let job = await api.createEnvironmentJob("stations", data.latitude, data.longitude);
      while (job.status === "pending" || job.status === "running") {
        setStationProgress(job.progress_label || "Esperando inicio");
        await new Promise((resolve) => window.setTimeout(resolve, 500));
        job = await api.getEnvironmentJob(job.id);
      }
      if (job.status === "failed" || !job.result) throw new Error(job.error || "La consulta SMN falló.");
      const estimate = job.result as unknown as StationEstimate;
      setStationEstimate(estimate);
      setStationSelection("combined");
      applyStationStatistics(estimate.combined, "Promedio combinado ponderado", estimate);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "No se pudieron estimar los valores de estaciones SMN.");
    } finally {
      setEstimatingStations(false);
      setStationProgress("");
    }
  };

  const selectStation = (selection: string) => {
    if (!stationEstimate) return;
    setStationSelection(selection);
    const statistics = selection === "combined"
      ? stationEstimate.combined
      : stationEstimate.stations.find((station) => station.code === selection);
    if (statistics) {
      const label = selection === "combined" ? "Promedio combinado ponderado" : stationEstimate.stations.find((station) => station.code === selection)?.name ?? selection;
      applyStationStatistics(statistics, label, stationEstimate);
    }
  };

  const save = async () => {
    const allErrors = [0, 1, 2].flatMap((index) => validateStep(index, data));
    setErrors(allErrors);
    if (allErrors.length) return;
    setSaving(true);
    setApiError("");
    try {
      let projectId = existingProjectId;
      if (!projectId) {
        const project = await api.createProject({
          name: data.projectName,
          description: data.projectDescription,
          responsible: data.responsible,
        });
        projectId = project.id;
      }
      const scenario = await api.createScenario(projectId, data.scenarioName, definition);
      setSavedScenario(scenario);
      await loadProjects();
      await loadScenarios(projectId);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "No se pudo guardar el escenario.");
    } finally {
      setSaving(false);
    }
  };

  const credentialsDialog = (
    <CredentialsDialog
      open={credentialsOpen}
      status={credentialStatus}
      form={credentialForm}
      saving={savingCredentials}
      onFormChange={setCredentialForm}
      onClose={() => setCredentialsOpen(false)}
      onSave={() => void saveCredentials()}
    />
  );

  if (activeResult) {
    return (
      <>
        <ResultsView
          initialRun={activeResult.run}
          scenario={activeResult.scenario}
          onRunChanged={updateActiveRun}
          onCredentials={() => setCredentialsOpen(true)}
          onBack={() => { setActiveResult(null); setWizardOpen(false); }}
        />
        {credentialsDialog}
      </>
    );
  }

  if (!wizardOpen) {
    return (
      <div className="app-shell">
        <header className="topbar">
          <div className="brand-mark"><Wind size={24} /></div>
          <div><strong>AERMOD</strong><span>Argentina · Screening + Horario</span></div>
          <button className="credentials-button" onClick={() => setCredentialsOpen(true)}><KeyRound size={15} /> Credenciales <i className={credentialStatus?.earthdata_configured && credentialStatus?.cds_configured ? "ready" : "missing"} /></button>
          <div className="engine-status"><i /> Motor validado <b>EPA 26135</b></div>
        </header>
        <main className="dashboard">
          <section className="hero">
            <div>
              <p className="eyebrow">ESPACIO DE TRABAJO</p>
              <h1>Proyectos de dispersión</h1>
              <p>Configurá fuentes puntuales para screening conservador o meteorología horaria observada, con trazabilidad completa.</p>
            </div>
            <button className="primary" onClick={startNew}><Plus size={18} /> Nuevo proyecto</button>
          </section>
          {apiError && <div className="alert error"><AlertCircle size={18} />{apiError}<button onClick={() => void loadProjects()}><RefreshCw size={15} /> Reintentar</button></div>}
          {dashboardLoading ? (
            <div className="loading"><LoaderCircle className="spin" /> Cargando proyectos…</div>
          ) : projects.length === 0 ? (
            <section className="empty-state">
              <div className="empty-icon"><FolderPlus size={32} /></div>
              <h2>Tu primer escenario está a un paso</h2>
              <p>Usá el caso EPA como referencia o empezá con los datos de una fuente propia.</p>
              <button className="secondary" onClick={startNew}>Crear proyecto</button>
            </section>
          ) : (
            <section className="project-grid">
              {projects.map((project) => (
                <article className="project-card" key={project.id}>
                  <div className="project-head"><span>PROYECTO</span><time>{new Date(project.created_at).toLocaleDateString("es-AR")}</time></div>
                  <h2>{project.name}</h2>
                  <p>{project.description || "Sin descripción"}</p>
                  <div className="card-actions">
                    <button className="text-button" onClick={() => void loadScenarios(project.id)}>Ver escenarios</button>
                    <span>{project.responsible || "Sin responsable"}</span>
                  </div>
                  {scenarios[project.id] && (
                    <div className="scenario-list">
                      {scenarios[project.id].length === 0 && <small>No hay escenarios guardados.</small>}
                      {scenarios[project.id].map((scenario) => (
                        <div key={scenario.id} className="scenario-item">
                          <span><Gauge size={15} />{scenario.name}<small>{isMultiSourceHourlyDefinition(scenario.definition) ? `MULTIFUENTE · ${scenario.definition.sources.length} FUENTES` : isHourlyDefinition(scenario.definition) ? "HORARIO 2024" : "SCREENING"} · {runs[scenario.id]?.[0]?.status === "completed" ? "Resultado disponible" : runs[scenario.id]?.[0]?.status === "failed" ? "Con error" : "Sin ejecutar"}</small></span>
                          <div className="scenario-actions">
                            {runs[scenario.id]?.[0]?.status === "completed" && <button className="view-result" onClick={() => setActiveResult({ scenario, run: runs[scenario.id][0] })}>Ver resultado</button>}
                            <button disabled={launchingScenarioId != null || preparingTerrain} onClick={() => void executeScenario(scenario)}>{launchingScenarioId === scenario.id || (preparingTerrain && launchingScenarioId == null) ? <LoaderCircle className="spin" size={15} /> : <Wind size={15} />} {launchingScenarioId === scenario.id || (preparingTerrain && launchingScenarioId == null) ? ("terrain" in scenario.definition && scenario.definition.terrain.mode === "complex" ? "Preparando terreno…" : "Iniciando…") : "Ejecutar"}</button>
                            <button onClick={() => startClone(project, scenario)} title="Duplicar escenario"><ClipboardCopy size={15} /></button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </article>
              ))}
            </section>
          )}
        </main>
        {credentialsOpen && <div className="credentials-modal" role="dialog" aria-modal="true" aria-label="Configuración de credenciales"><section className="credentials-panel"><header><div className="credential-icon"><KeyRound size={24} /></div><div><p className="eyebrow">CONFIGURACIÓN LOCAL</p><h2>Acceso a datos ambientales</h2><p>Iniciá sesión en cada proveedor, obtené tus credenciales y pegalas aquí. La aplicación nunca vuelve a mostrarlas.</p></div></header><div className="credential-provider"><div><strong>NASA Earthdata</strong><span>Necesario para descargar albedo MODIS mediante AppEEARS.</span><a href="https://urs.earthdata.nasa.gov/users" target="_blank" rel="noreferrer">Iniciar sesión o crear cuenta ↗</a></div><em className={credentialStatus?.earthdata_configured ? "configured" : "pending"}>{credentialStatus?.earthdata_configured ? "CONFIGURADO" : "PENDIENTE"}</em></div><div className="credential-fields"><label><span>Usuario Earthdata</span><input placeholder={credentialStatus?.earthdata_configured ? "Dejar vacío para conservar" : "Usuario"} value={credentialForm.earthdata_username} onChange={(event) => setCredentialForm((current) => ({ ...current, earthdata_username: event.target.value }))} autoComplete="username" /></label><label><span>Contraseña Earthdata</span><input placeholder={credentialStatus?.earthdata_configured ? "Dejar vacío para conservar" : "Contraseña"} type="password" value={credentialForm.earthdata_password} onChange={(event) => setCredentialForm((current) => ({ ...current, earthdata_password: event.target.value }))} autoComplete="current-password" /></label></div><div className="credential-provider"><div><strong>Copernicus Climate Data Store</strong><span>Necesario para descargar los flujos ERA5-Land.</span><a href="https://cds.climate.copernicus.eu/how-to-api" target="_blank" rel="noreferrer">Iniciar sesión y copiar el Personal Access Token ↗</a></div><em className={credentialStatus?.cds_configured ? "configured" : "pending"}>{credentialStatus?.cds_configured ? "CONFIGURADO" : "PENDIENTE"}</em></div><div className="credential-fields single"><label><span>Personal Access Token de CDS</span><input placeholder={credentialStatus?.cds_configured ? "Dejar vacío para conservar" : "Token personal"} type="password" value={credentialForm.cdsapi_key} onChange={(event) => setCredentialForm((current) => ({ ...current, cdsapi_key: event.target.value }))} autoComplete="off" /></label></div><div className="credential-security"><ShieldCheck size={18} /><span>En Windows se guardan en Credential Manager, dentro del perfil del usuario. No se incluyen en proyectos, resultados ni archivos exportados.</span></div><footer><button className="secondary" onClick={() => setCredentialsOpen(false)}>Ahora no</button><button className="primary" disabled={savingCredentials || (!credentialForm.cdsapi_key && !credentialForm.earthdata_username) || Boolean(credentialForm.earthdata_username) !== Boolean(credentialForm.earthdata_password)} onClick={() => void saveCredentials()}>{savingCredentials ? <LoaderCircle className="spin" size={16} /> : <KeyRound size={16} />} Guardar credenciales</button></footer></section></div>}
      </div>
    );
  }

  return (
    <div className="wizard-shell">
      <header className="topbar">
        <button className="back-dashboard" onClick={() => setWizardOpen(false)}><ArrowLeft size={18} /> Proyectos</button>
        <div className="brand-center"><Wind size={20} /> AERMOD · {data.runMode === "multi_source_hourly" ? "Multifuente" : data.runMode === "hourly" ? "Horario" : "Screening"}</div>
        <button className="credentials-button wizard-credentials" onClick={() => setCredentialsOpen(true)}><KeyRound size={15} /> Credenciales <i className={credentialStatus?.earthdata_configured && credentialStatus?.cds_configured ? "ready" : "missing"} /></button>
        <span className="draft-label">BORRADOR</span>
      </header>
      <div className="wizard-layout">
        <aside className="stepper">
          <p className="eyebrow">NUEVO ESCENARIO</p>
          <h2>{data.scenarioName || "Sin nombre"}</h2>
          <nav>
            {STEPS.map(({ label, icon: Icon }, index) => (
              <button key={label} className={index === step ? "active" : index < step ? "done" : ""} onClick={() => index < step && setStep(index)}>
                <span>{index < step ? <Check size={17} /> : <Icon size={17} />}</span>
                <div><b>0{index + 1}</b>{label}</div>
              </button>
            ))}
          </nav>
          <div className="scope-note"><Settings2 size={18} /><div><strong>Alcance actual</strong><span>{data.runMode === "multi_source_hourly" ? `Horario 2024 · ${data.multiSources.length} fuentes · Terreno ${data.terrainMode === "complex" ? "complejo" : "plano"} · Sin downwash` : data.runMode === "hourly" ? `Horario 2024 · Fuente puntual · Terreno ${data.terrainMode === "complex" ? "complejo" : "plano"} · ${data.downwashEnabled ? "Con downwash" : "Sin downwash"}` : `Screening · Fuente puntual · Terreno ${data.terrainMode === "complex" ? "complejo" : "plano"} · ${data.downwashEnabled ? "Con downwash" : "Sin downwash"}`}</span></div></div>
        </aside>
        <main className="wizard-main">
          {savedScenario ? (
            <section className="success-panel">
              <div><Check size={30} /></div>
              <p className="eyebrow">ESCENARIO GUARDADO</p>
              <h1>{savedScenario.name}</h1>
              <p>La definición quedó validada y guardada. El escenario está listo para {"terrain" in savedScenario.definition && savedScenario.definition.terrain.mode === "complex" ? "preparar las elevaciones con AERMAP y ejecutar el modelo" : "ejecutar el modelo y visualizar los resultados"}.</p>
              <code>{savedScenario.id}</code>
              {terrainPreparation && <div className="terrain-result"><strong>Terreno preparado</strong><span>UTM {terrainPreparation.utm_zone} {terrainPreparation.utm_hemisphere === "south" ? "Sur" : "Norte"}</span>{terrainPreparation.source_elevations_m ? Object.entries(terrainPreparation.source_elevations_m).map(([sourceId, elevation]) => <span key={sourceId}>{sourceId}: {elevation.toFixed(2)} m</span>) : <span>Elevación: {terrainPreparation.source_elevation_m?.toFixed(2)} m</span>}<span>{terrainPreparation.receptor_count} receptores</span></div>}
              <div className="success-actions"><button className="secondary" onClick={() => setWizardOpen(false)}>Volver a proyectos</button><button className="primary" disabled={preparingTerrain} onClick={() => void executeScenario(savedScenario)}>{preparingTerrain ? <LoaderCircle className="spin" size={17} /> : <Wind size={17} />} {"terrain" in savedScenario.definition && savedScenario.definition.terrain.mode === "complex" ? "Preparar terreno y ejecutar" : "Ejecutar ahora"}</button></div>
            </section>
          ) : (
            <>
              <div className="form-heading">
                <p className="eyebrow">PASO {step + 1} DE 4</p>
                <h1>{["Identificación del estudio", data.runMode === "multi_source_hourly" ? "Fuentes puntuales" : "Parámetros de la fuente", data.runMode !== "screening" ? "Meteorología horaria" : "Condiciones de screening", "Revisar antes de guardar"][step]}</h1>
                <p>{[
                  "Organizá el escenario dentro de un proyecto trazable.",
                  "Ingresá las características físicas y la emisión de la chimenea.",
                  data.runMode !== "screening" ? "Elegí el conjunto NOAA/AERMET y la red radial cronológica." : "Definí superficie, atmósfera y red de búsqueda conservadora.",
                  "Confirmá los valores canónicos que recibirá el motor.",
                ][step]}</p>
              </div>
              {errors.length > 0 && <div className="alert error"><AlertCircle size={18} /><div>{errors.map((error) => <p key={error}>{error}</p>)}</div></div>}
              {apiError && <div className="alert error"><AlertCircle size={18} />{apiError}</div>}
              {step === 0 && (
                <section className="form-card">
                  <div className="section-title"><span>01</span><div><h2>Proyecto</h2><p>Información administrativa del estudio.</p></div></div>
                  <div className="form-grid two">
                    <Field label="Nombre del proyecto" value={data.projectName} onChange={(v) => update("projectName", v)} />
                    <Field label="Responsable" value={data.responsible} onChange={(v) => update("responsible", v)} help="Opcional" />
                    <label className="field full"><span className="field-label">Descripción<span className="help-tip" tabIndex={0} aria-label="Ayuda: Descripción"><Info size={13} /><span role="tooltip">Propósito, alcance y supuestos principales del proyecto.</span></span></span><textarea value={data.projectDescription} onChange={(e) => update("projectDescription", e.target.value)} rows={3} /></label>
                  </div>
                  <div className="section-divider" />
                  <div className="section-title"><span>02</span><div><h2>Escenario</h2><p>Nombre que diferencie esta configuración.</p></div></div>
                  <Field label="Nombre del escenario" value={data.scenarioName} onChange={(v) => update("scenarioName", v)} />
                  <div className="section-divider" />
                  <div className="section-title"><span>03</span><div><h2>Modalidad de cálculo</h2><p>Ambas modalidades permanecen disponibles como flujos independientes.</p></div></div>
                  <div className="mode-toggle">
                    <button className={data.runMode === "screening" ? "selected" : ""} onClick={() => selectRunMode("screening")}><b>Screening</b><small>MAKEMET · peor caso conservador</small></button>
                    <button className={data.runMode === "hourly" ? "selected" : ""} onClick={() => selectRunMode("hourly")}><b>Horario 2024</b><small>NOAA + AERMET · secuencia observada</small></button>
                    <button className={data.runMode === "multi_source_hourly" ? "selected" : ""} onClick={() => selectRunMode("multi_source_hourly")}><b>Multifuente horario</b><small>Aportes combinados · grupo ALL</small></button>
                  </div>
                  <div className="surface-source-note"><Info size={18} /><div><strong>Flujos independientes</strong><p>Screening conserva la búsqueda sintética de peor caso. Horario procesa una fuente sobre una secuencia observada. Multifuente combina dos o más fuentes con esa meteorología y admite terreno plano o complejo; downwash multifuente todavía no está incluido.</p></div></div>
                </section>
              )}
              {step === 1 && (
                <section className="form-card">
                  {data.runMode === "multi_source_hourly" ? <>
                    <div className="section-title"><span>01</span><div><h2>Configuración común</h2><p>El contaminante y la meteorología se comparten entre todas las fuentes.</p></div></div>
                    <div className="form-grid two"><Field label="Contaminante" value={data.pollutantId} onChange={(v) => update("pollutantId", v.toUpperCase())} help="Ej.: PM10, SO2, OTHER" /></div>
                    <div className="section-divider" />
                    <div className="section-title"><span>02</span><div><h2>Inventario de fuentes</h2><p>Parámetros canónicos AERMOD: g/s, m, K y m/s. Todas las coordenadas son WGS84.</p></div></div>
                    <div className="multi-source-list">
                      {data.multiSources.map((source, index) => <article className="multi-source-card" key={`${index}-${source.sourceId}`}>
                        <header><strong>Fuente {index + 1}</strong><button type="button" className="secondary" disabled={data.multiSources.length <= 2} onClick={() => update("multiSources", data.multiSources.filter((_, sourceIndex) => sourceIndex !== index))}>Quitar</button></header>
                        <div className="form-grid three">
                          <Field label="ID de fuente" value={source.sourceId} onChange={(v) => updateMultiSource(index, "sourceId", v.toUpperCase())} help="Máximo 8 caracteres" />
                          <Field label="Emisión" type="number" min={0} step={0.01} value={source.emissionRate} onChange={(v) => updateMultiSource(index, "emissionRate", numeric(v))} unit={<span className="fixed-unit">g/s</span>} />
                          <Field label="Altura" type="number" min={0} step={0.1} value={source.stackHeight} onChange={(v) => updateMultiSource(index, "stackHeight", numeric(v))} unit={<span className="fixed-unit">m</span>} />
                          <Field label="Temperatura" type="number" min={0} step={0.1} value={source.stackTemperature} onChange={(v) => updateMultiSource(index, "stackTemperature", numeric(v))} unit={<span className="fixed-unit">K</span>} />
                          <Field label="Velocidad" type="number" min={0} step={0.1} value={source.exitVelocity} onChange={(v) => updateMultiSource(index, "exitVelocity", numeric(v))} unit={<span className="fixed-unit">m/s</span>} />
                          <Field label="Diámetro" type="number" min={0} step={0.01} value={source.stackDiameter} onChange={(v) => updateMultiSource(index, "stackDiameter", numeric(v))} unit={<span className="fixed-unit">m</span>} />
                          <Field label="Latitud" type="number" min={-90} step={0.000001} value={source.latitude} onChange={(v) => updateMultiSource(index, "latitude", numeric(v))} />
                          <Field label="Longitud" type="number" min={-180} step={0.000001} value={source.longitude} onChange={(v) => updateMultiSource(index, "longitude", numeric(v))} />
                        </div>
                      </article>)}
                    </div>
                    <button type="button" className="secondary add-source" disabled={data.multiSources.length >= 100} onClick={() => update("multiSources", [...data.multiSources, { ...data.multiSources[data.multiSources.length - 1], sourceId: `STACK${data.multiSources.length + 1}` }])}><Plus size={16} /> Agregar fuente</button>
                  </> : <>
                  <div className="section-title"><span>01</span><div><h2>Identificación</h2><p>Etiquetas compatibles con el archivo AERMOD.</p></div></div>
                  <div className="form-grid two">
                    <Field label="ID de fuente" value={data.sourceId} onChange={(v) => update("sourceId", v.toUpperCase())} help="Máximo 8 caracteres" />
                    <Field label="Contaminante" value={data.pollutantId} onChange={(v) => update("pollutantId", v.toUpperCase())} help="Ej.: PM10, SO2, OTHER" />
                    <Field label="Latitud" type="number" min={-90} step={0.000001} value={data.latitude} onChange={(v) => update("latitude", numeric(v))} help="Opcional · WGS84, grados decimales" />
                    <Field label="Longitud" type="number" min={-180} step={0.000001} value={data.longitude} onChange={(v) => update("longitude", numeric(v))} help="Opcional · WGS84, grados decimales" />
                  </div>
                  <div className="section-divider" />
                  <div className="section-title"><span>02</span><div><h2>Emisión y chimenea</h2><p>Podés elegir las unidades de ingreso.</p></div></div>
                  <div className="form-grid two">
                    <Field label="Tasa de emisión" type="number" min={0} step={0.01} value={data.emissionRate} onChange={(v) => update("emissionRate", numeric(v))} unit={<UnitSelect value={data.emissionUnit} options={["g/s", "kg/h"]} onChange={(v) => update("emissionUnit", v as WizardData["emissionUnit"])} />} />
                    <Field label="Altura de chimenea" type="number" min={0} step={0.1} value={data.stackHeight} onChange={(v) => update("stackHeight", numeric(v))} unit={<UnitSelect value={data.heightUnit} options={["m", "ft"]} onChange={(v) => update("heightUnit", v as WizardData["heightUnit"])} />} />
                    <Field label="Temperatura de salida" type="number" step={0.1} value={data.stackTemperature} onChange={(v) => update("stackTemperature", numeric(v))} unit={<UnitSelect value={data.temperatureUnit} options={["K", "°C"]} onChange={(v) => update("temperatureUnit", v as WizardData["temperatureUnit"])} />} />
                    <Field label="Velocidad de salida" type="number" min={0} step={0.1} value={data.exitVelocity} onChange={(v) => update("exitVelocity", numeric(v))} unit={<UnitSelect value={data.velocityUnit} options={["m/s", "km/h"]} onChange={(v) => update("velocityUnit", v as WizardData["velocityUnit"])} />} />
                    <Field label="Diámetro interior" type="number" min={0} step={0.01} value={data.stackDiameter} onChange={(v) => update("stackDiameter", numeric(v))} unit={<UnitSelect value={data.diameterUnit} options={["m", "cm"]} onChange={(v) => update("diameterUnit", v as WizardData["diameterUnit"])} />} />
                  </div>
                  </>}
                  {notices.length > 0 && <div className="alert warning"><AlertCircle size={18} /><div>{notices.map((notice) => <p key={notice}>{notice}</p>)}</div></div>}
                </section>
              )}
              {step === 2 && (
                <section className="form-card">
                  {data.runMode === "screening" ? <>
                  <div className="section-title"><span>01</span><div><h2>Entorno</h2><p>Clasificación y características de superficie.</p></div></div>
                  <div className="section-title"><span>T</span><div><h2>Terreno</h2><p>El modo complejo prepara elevaciones con AERMAP y evalúa sectores de 10°.</p></div></div>
                  <div className="mode-toggle">
                    <button className={data.terrainMode === "flat" ? "selected" : ""} onClick={() => update("terrainMode", "flat")}><b>Plano</b><small>Elevación uniforme ingresada</small></button>
                    <button className={data.terrainMode === "complex" ? "selected" : ""} onClick={() => update("terrainMode", "complex")}><b>Complejo</b><small>Modelo digital de elevación</small></button>
                  </div>
                  {data.terrainMode === "complex" && <><label className="field terrain-provider"><span className="field-label">Proveedor del modelo de elevación</span><span className="input-wrap"><select value={data.terrainProvider} onChange={(event) => update("terrainProvider", event.target.value as WizardData["terrainProvider"])}><option value="copernicus">Copernicus GLO-30 (automático)</option><option value="ign" disabled>IGN MDE-Ar (carga manual, próxima etapa)</option></select></span><small>Copernicus es un DSM de 30 m y puede incluir vegetación o construcciones.</small></label><label className="check-row" title="Ejecuta además el mismo escenario con elevación uniforme para aislar el efecto del terreno."><input type="checkbox" checked={data.compareTerrainWithFlat} onChange={(event) => update("compareTerrainWithFlat", event.target.checked)} /><span><b>Comparar con terreno plano</b><small>Agrega una corrida de control con la misma fuente, meteorología, receptores y downwash.</small></span></label></>}
                  <div className="section-divider" />
                  <div className="section-title"><span>B</span><div><h2>Influencia de edificios</h2><p>BPIPPRM calcula las dimensiones PRIME para evaluar downwash.</p></div></div>
                  <label className="check-row" title="Incluye el efecto aerodinámico del edificio sobre la pluma mediante BPIPPRM y PRIME."><input type="checkbox" checked={data.downwashEnabled} onChange={(event) => update("downwashEnabled", event.target.checked)} /><span><b>Activar downwash</b><small>Compatible con terreno plano o complejo procesado por AERMAP.</small></span></label>
                  {data.downwashEnabled && <><div className="form-grid three compact-top">
                    <Field label="ID de edificio" value={data.buildingId} onChange={(value) => update("buildingId", value.toUpperCase())} />
                    <Field label="Altura del edificio" type="number" min={0} step={0.1} value={data.buildingHeight} onChange={(value) => update("buildingHeight", numeric(value))} unit={<span className="fixed-unit">m</span>} />
                    {data.terrainMode === "flat" && <Field label="Elevación base" type="number" step={0.1} value={data.buildingBaseElevation} onChange={(value) => update("buildingBaseElevation", numeric(value))} unit={<span className="fixed-unit">m</span>} />}
                    <Field label="Centro Este" type="number" step={0.1} value={data.buildingCenterEast} onChange={(value) => update("buildingCenterEast", numeric(value))} unit={<span className="fixed-unit">m</span>} />
                    <Field label="Centro Norte" type="number" step={0.1} value={data.buildingCenterNorth} onChange={(value) => update("buildingCenterNorth", numeric(value))} unit={<span className="fixed-unit">m</span>} />
                    <Field label="Largo" type="number" min={0} step={0.1} value={data.buildingLength} onChange={(value) => update("buildingLength", numeric(value))} unit={<span className="fixed-unit">m</span>} />
                    <Field label="Ancho" type="number" min={0} step={0.1} value={data.buildingWidth} onChange={(value) => update("buildingWidth", numeric(value))} unit={<span className="fixed-unit">m</span>} />
                    <Field label="Rotación" type="number" step={1} value={data.buildingRotation} onChange={(value) => update("buildingRotation", numeric(value))} unit={<span className="fixed-unit">°</span>} />
                  </div>{data.terrainMode === "complex" && <div className="surface-source-note"><Info size={18} /><div><strong>Cotas de base automáticas</strong><p>AERMAP asignará la elevación del terreno a la base de la chimenea y del edificio. Las alturas físicas sobre el terreno continúan siendo datos de entrada y no pueden deducirse de forma confiable del DEM.</p></div></div>}<BuildingPreview data={data} /><div className="surface-source-note"><Info size={18} /><div><strong>Geometría respecto de la chimenea</strong><p>La chimenea ocupa el origen (0, 0). Ingresá centro, dimensiones y giro de una planta rectangular. En un caso real estos valores se obtienen de planos, relevamiento topográfico, GIS o imágenes de alta resolución, y deben verificarse en campo.</p></div></div></>}
                  <div className="section-divider" />
                  <div className="mode-toggle">
                    {(["rural", "urban"] as const).map((mode) => <button key={mode} title={mode === "rural" ? "Usa la formulación rural de dispersión; corresponde a entornos sin predominio urbano en el área de influencia." : "Usa la formulación urbana de AERMOD y requiere una población representativa del área urbana."} className={data.dispersionMode === mode ? "selected" : ""} onClick={() => update("dispersionMode", mode)}>{mode === "rural" ? "Rural" : "Urbano"}<small>{mode === "rural" ? "Baja densidad construida" : "Área construida consolidada"}</small></button>)}
                  </div>
                  {data.dispersionMode === "urban" && <Field label="Población urbana" type="number" min={1} value={data.urbanPopulation} onChange={(v) => update("urbanPopulation", numeric(v))} />}
                  <div className="form-grid three compact-top">
                    <Field label="Albedo" type="number" min={0} step={0.01} value={data.albedo} onChange={(v) => update("albedo", numeric(v))} help={surfaceHelp?.albedo ?? "0,14 proviene del caso EPA. Real: cobertura del suelo + estación/mes, con tablas tipo AERSURFACE o teledetección documentada."} />
                    <Field label="Razón de Bowen" type="number" min={0} step={0.01} value={data.bowenRatio} onChange={(v) => update("bowenRatio", numeric(v))} help={surfaceHelp?.bowen ?? "0,63 proviene del caso EPA. Real: cobertura del suelo, estación y condición de humedad; estimable con metodología AERSURFACE adaptada a datos locales."} />
                    <Field label="Rugosidad" type="number" min={0} step={0.001} value={data.surfaceRoughness} onChange={(v) => update("surfaceRoughness", numeric(v))} unit={<span className="fixed-unit">m</span>} help={surfaceHelp?.roughness ?? "0,128 m proviene del caso EPA. Real: cobertura y altura/densidad de obstáculos alrededor de la fuente, idealmente por sectores."} />
                  </div>
                  <div className="local-surface-action"><button className="secondary" type="button" disabled={estimatingSurface} onClick={() => void estimateSurface()}>{estimatingSurface ? <LoaderCircle className="spin" size={17} /> : <RefreshCw size={17} />} Obtener valores locales</button><span>{surfaceProgress || "Usa las coordenadas de la fuente y los dos últimos meses completos."}</span></div>
                  {surfaceEstimate && <div className={`surface-estimate-result ${surfaceEstimate.meets_minimum_coverage ? "" : "quality-rejected"}`}><strong>{surfaceEstimate.meets_minimum_coverage ? "Valores locales aplicados" : "Valores locales no aplicados"}</strong><span>Período exacto: {surfaceEstimate.period_start} a {surfaceEstimate.period_end}</span><span>MODIS: {surfaceEstimate.albedo_valid_count}/{surfaceEstimate.albedo_expected_count} observaciones ({surfaceEstimate.albedo_coverage_percent.toFixed(1)} %) · faltan {surfaceEstimate.albedo_missing_count}</span><span>ERA5-Land: {surfaceEstimate.bowen_valid_count}/{surfaceEstimate.bowen_expected_count} horas ({surfaceEstimate.bowen_coverage_percent.toFixed(1)} %) · faltan {surfaceEstimate.bowen_missing_count}</span><span>Rugosidad crítica: sector {surfaceEstimate.selected_roughness_direction_deg}°</span>{surfaceEstimate.warnings.map((warning) => <span className="surface-warning" key={warning}>{warning}</span>)}</div>}
                  <div className="surface-source-note"><Info size={18} /><div><strong>¿De dónde obtener valores reales?</strong><p>La aplicación usa MODIS MCD43A3 para albedo, los flujos de ERA5-Land para Bowen y ESA WorldCover para 36 sectores de rugosidad. Los valores quedan editables antes de ejecutar.</p><a href="https://gaftp.epa.gov/Air/aqmg/SCRAM/models/related/aersurface/aersurface_userguide.pdf" target="_blank" rel="noreferrer">Guía oficial AERSURFACE ↗</a></div></div>
                  <div className="section-divider" />
                  <div className="section-title"><span>02</span><div><h2>Meteorología sintética</h2><p>Matriz de peor caso generada por MAKEMET.</p></div></div>
                  <div className="form-grid three">
                    <Field label="Temperatura mínima" type="number" step={1} value={data.minimumTemperature} onChange={(v) => update("minimumTemperature", numeric(v))} unit={<span className="fixed-unit">K</span>} />
                    <Field label="Temperatura máxima" type="number" step={1} value={data.maximumTemperature} onChange={(v) => update("maximumTemperature", numeric(v))} unit={<span className="fixed-unit">K</span>} />
                    <Field label="Viento mínimo" type="number" min={0} step={0.1} value={data.minimumWindSpeed} onChange={(v) => update("minimumWindSpeed", numeric(v))} unit={<span className="fixed-unit">m/s</span>} />
                    <Field label="Altura anemómetro" type="number" min={0} step={0.1} value={data.anemometerHeight} onChange={(v) => update("anemometerHeight", numeric(v))} unit={<span className="fixed-unit">m</span>} />
                    <Field label="Dirección" type="number" min={0} step={1} value={data.windDirection} onChange={(v) => update("windDirection", numeric(v))} unit={<span className="fixed-unit">°</span>} />
                  </div>
                  <div className="station-action"><button className="secondary" type="button" disabled={estimatingStations} onClick={() => void estimateStations()}>{estimatingStations ? <LoaderCircle className="spin" size={17} /> : <RefreshCw size={17} />} Obtener estaciones SMN</button>{stationProgress && <small>{stationProgress}</small>}{stationEstimate && <label><span>Aplicar</span><select value={stationSelection} onChange={(event) => selectStation(event.target.value)}><option value="combined">Promedio combinado</option>{stationEstimate.stations.map((station) => <option key={station.code} value={station.code}>{station.name}</option>)}</select></label>}</div>
                  {stationEstimate && <div className="station-results"><header><strong>Observaciones SMN{stationEstimate.region ? ` · ${stationEstimate.region}` : ""} · {stationEstimate.period_start} a {stationEstimate.period_end}</strong><small>Valores aplicados en K y m/s; medias en °C sólo como diagnóstico.</small></header>{stationEstimate.stations.map((station) => <article key={station.code}><b>{station.name} · OMM {station.code}</b><span>{station.distance_to_source_km.toFixed(1)} km · {station.elevation_m.toFixed(0)} m s.n.m.</span><span>Cobertura {station.coverage_percent.toFixed(1)} % ({station.observation_count}/{station.expected_hour_count})</span><span>Temperatura media {station.temperature_mean_c.toFixed(2)} °C · rango {station.temperature_min_c.toFixed(1)}–{station.temperature_max_c.toFixed(1)} °C</span><span>Viento medio {station.wind_mean_m_s.toFixed(2)} m/s · P1/P5/P95/P99: {station.wind_p01_m_s.toFixed(2)} / {station.wind_p05_m_s.toFixed(2)} / {station.wind_p95_m_s.toFixed(2)} / {station.wind_p99_m_s.toFixed(2)} m/s</span></article>)}<article className="combined"><b>Promedio combinado ponderado</b><span>Cobertura {stationEstimate.combined.coverage_percent.toFixed(1)} % ({stationEstimate.combined.observation_count}/{stationEstimate.combined.expected_hour_count})</span><span>Temperatura media {stationEstimate.combined.temperature_mean_c.toFixed(2)} °C · rango {stationEstimate.combined.temperature_min_c.toFixed(1)}–{stationEstimate.combined.temperature_max_c.toFixed(1)} °C</span><span>Viento MAKEMET: {stationEstimate.combined.makemet_minimum_wind_m_s.toFixed(2)} m/s</span></article>{stationEstimate.warnings.map((warning) => <small className="surface-warning" key={warning}>{warning}</small>)}</div>}
                  <label className="check-row" title="Activa el ajuste de velocidad de fricción mínima implementado por MAKEMET para condiciones estables de viento débil."><input type="checkbox" checked={data.adjustFrictionVelocity} onChange={(e) => update("adjustFrictionVelocity", e.target.checked)} /><span><b>Ajustar velocidad de fricción (u*)</b><small>Aplicar el algoritmo de ajuste incluido en MAKEMET.</small></span></label>
                  <div className="section-divider" />
                  <div className="section-title"><span>03</span><div><h2>Receptores</h2><p>Rango donde se buscará la máxima concentración.</p></div></div>
                  <div className="form-grid three">
                    <Field label="Límite ambiental" type="number" min={0} value={data.ambientBoundaryDistance} onChange={(v) => update("ambientBoundaryDistance", numeric(v))} unit={<span className="fixed-unit">m</span>} />
                    <Field label="Inicio búsqueda" type="number" min={0} value={data.searchStart} onChange={(v) => update("searchStart", numeric(v))} unit={<span className="fixed-unit">m</span>} />
                    <Field label="Fin búsqueda" type="number" min={0} value={data.searchEnd} onChange={(v) => update("searchEnd", numeric(v))} unit={<span className="fixed-unit">m</span>} />
                    <Field label="Paso" type="number" min={0} value={data.searchStep} onChange={(v) => update("searchStep", numeric(v))} unit={<span className="fixed-unit">m</span>} />
                    <Field label="Elevación base" type="number" value={data.baseElevation} onChange={(v) => update("baseElevation", numeric(v))} unit={<span className="fixed-unit">m</span>} />
                    <Field label="Altura receptor" type="number" min={0} value={data.receptorHeight} onChange={(v) => update("receptorHeight", numeric(v))} unit={<span className="fixed-unit">m</span>} />
                  </div>
                  </> : <>
                    <div className="section-title"><span>01</span><div><h2>Conjunto meteorológico</h2><p>Datos horarios 2024 ya procesados y controlados con AERMET 26135.</p></div></div>
                    <div className="form-grid two">
                      <label className="field"><span className="field-label">Estación NOAA/AERMET</span><span className="input-wrap"><select value={data.hourlyStation} onChange={(event) => update("hourlyStation", event.target.value as WizardData["hourlyStation"])}><option value="cordoba-aero">Córdoba Aero · OMM 87344</option><option value="mendoza-aero">Mendoza Aero · OMM 87418</option></select></span><small>Superficie NOAA ISD + perfiles verticales NOAA IGRA.</small></label>
                      <Field label="Año" type="number" value={data.hourlyYear} onChange={(value) => update("hourlyYear", numeric(value))} help="Período disponible y validado: 2024 completo" />
                    </div>
                    <div className="surface-source-note"><Info size={18} /><div><strong>Calidad conocida</strong><p>Córdoba tiene 8.095/8.784 horas utilizables (92,16 %). Mendoza tiene 5.932/8.784 (67,53 %) y conserva sus calmas y faltantes reales. La corrida no rellena horas artificialmente.</p></div></div>
                    <div className="section-divider" />
                    <div className="section-title"><span>02</span><div><h2>Clasificación de dispersión</h2><p>AERMOD utiliza la secuencia meteorológica observada seleccionada.</p></div></div>
                    <div className="mode-toggle">
                      {(["rural", "urban"] as const).map((mode) => <button key={mode} className={data.dispersionMode === mode ? "selected" : ""} onClick={() => update("dispersionMode", mode)}><b>{mode === "rural" ? "Rural" : "Urbano"}</b><small>{mode === "rural" ? "Baja densidad construida" : "Requiere población representativa"}</small></button>)}
                    </div>
                    {data.dispersionMode === "urban" && <Field label="Población urbana" type="number" min={1} value={data.urbanPopulation} onChange={(value) => update("urbanPopulation", numeric(value))} />}
                    <div className="section-divider" />
                    <div className="section-title"><span>T</span><div><h2>Terreno</h2><p>La opción compleja asigna cotas reales a fuente y receptores con AERMAP.</p></div></div>
                    <div className="mode-toggle">
                      <button className={data.terrainMode === "flat" ? "selected" : ""} onClick={() => update("terrainMode", "flat")}><b>Plano</b><small>Coordenadas relativas sin elevación</small></button>
                      <button className={data.terrainMode === "complex" ? "selected" : ""} onClick={() => update("terrainMode", "complex")}><b>Complejo</b><small>Copernicus GLO-30 + AERMAP</small></button>
                    </div>
                    {data.terrainMode === "complex" && <label className="field terrain-provider"><span className="field-label">Proveedor del modelo de elevación</span><span className="input-wrap"><select value={data.terrainProvider} onChange={(event) => update("terrainProvider", event.target.value as WizardData["terrainProvider"])}><option value="copernicus">Copernicus GLO-30 (automático)</option></select></span><small>Se conserva el archivo DEM, su hash y las salidas de AERMAP para auditoría.</small></label>}
                    {data.runMode === "hourly" && <><div className="section-divider" />
                    <div className="section-title"><span>B</span><div><h2>Influencia de edificios</h2><p>BPIPPRM calcula 36 juegos de parámetros PRIME para toda la secuencia horaria.</p></div></div>
                    <label className="check-row"><input type="checkbox" checked={data.downwashEnabled} onChange={(event) => update("downwashEnabled", event.target.checked)} /><span><b>Activar downwash horario</b><small>Ejecuta además un control cronológico idéntico sin PRIME para comparar los cinco períodos.</small></span></label>
                    {data.downwashEnabled && <><div className="form-grid three compact-top">
                      <Field label="ID de edificio" value={data.buildingId} onChange={(value) => update("buildingId", value.toUpperCase())} />
                      <Field label="Altura del edificio" type="number" min={0} step={0.1} value={data.buildingHeight} onChange={(value) => update("buildingHeight", numeric(value))} unit={<span className="fixed-unit">m</span>} />
                      <Field label="Centro Este" type="number" step={0.1} value={data.buildingCenterEast} onChange={(value) => update("buildingCenterEast", numeric(value))} unit={<span className="fixed-unit">m</span>} />
                      <Field label="Centro Norte" type="number" step={0.1} value={data.buildingCenterNorth} onChange={(value) => update("buildingCenterNorth", numeric(value))} unit={<span className="fixed-unit">m</span>} />
                      <Field label="Largo" type="number" min={0} step={0.1} value={data.buildingLength} onChange={(value) => update("buildingLength", numeric(value))} unit={<span className="fixed-unit">m</span>} />
                      <Field label="Ancho" type="number" min={0} step={0.1} value={data.buildingWidth} onChange={(value) => update("buildingWidth", numeric(value))} unit={<span className="fixed-unit">m</span>} />
                      <Field label="Rotación" type="number" step={1} value={data.buildingRotation} onChange={(value) => update("buildingRotation", numeric(value))} unit={<span className="fixed-unit">°</span>} />
                    </div><BuildingPreview data={data} /><div className="surface-source-note"><Info size={18} /><div><strong>Cota de base</strong><p>{data.terrainMode === "complex" ? "AERMAP asigna la cota de la fuente también al edificio; la altura física y la planta continúan siendo datos ingresados." : "En terreno plano, fuente y edificio se consideran coplanares; la altura física y la planta son los datos relevantes para BPIPPRM."}</p></div></div></>}
                    </>}
                    <div className="section-divider" />
                    <div className="section-title"><span>03</span><div><h2>Receptores omnidireccionales</h2><p>Cada distancia se evalúa alrededor de la fuente para respetar los vientos cronológicos.</p></div></div>
                    <div className="form-grid three">
                      <Field label="Límite ambiental" type="number" min={0} value={data.ambientBoundaryDistance} onChange={(v) => update("ambientBoundaryDistance", numeric(v))} unit={<span className="fixed-unit">m</span>} />
                      <Field label="Inicio búsqueda" type="number" min={0} value={data.searchStart} onChange={(v) => update("searchStart", numeric(v))} unit={<span className="fixed-unit">m</span>} />
                      <Field label="Fin búsqueda" type="number" min={0} value={data.searchEnd} onChange={(v) => update("searchEnd", numeric(v))} unit={<span className="fixed-unit">m</span>} />
                      <Field label="Paso" type="number" min={0} value={data.searchStep} onChange={(v) => update("searchStep", numeric(v))} unit={<span className="fixed-unit">m</span>} />
                      <Field label="Paso angular" type="number" min={1} value={data.directionStep} onChange={(v) => update("directionStep", numeric(v))} unit={<span className="fixed-unit">°</span>} help="Debe dividir exactamente 360°; 10° genera 36 direcciones." />
                      <Field label="Altura receptor" type="number" min={0} value={data.receptorHeight} onChange={(v) => update("receptorHeight", numeric(v))} unit={<span className="fixed-unit">m</span>} />
                    </div>
                    <div className="alert warning"><AlertCircle size={18} /><div><p>{data.runMode === "multi_source_hourly" ? "Los contornos representan la concentración combinada de todas las fuentes en cada receptor. En terreno complejo, AERMAP procesa todas las chimeneas y receptores dentro de un único dominio; downwash todavía no está incluido." : "La corrida horaria usa una sola secuencia cronológica sobre toda la red. Si activás downwash, BPIPPRM/PRIME se aplica directamente y se genera un control sin downwash; no interviene MAKEMET ni el modo SCREEN."}</p></div></div>
                  </>}
                </section>
              )}
              {step === 3 && (
                <section className="review-grid">
                  {isMultiSourceHourlyDefinition(definition) ? <article className="review-card"><header><Factory size={18} /><h2>{definition.sources.length} fuentes puntuales</h2><button onClick={() => setStep(1)}>Editar</button></header><SummaryRow label="Contaminante" value={definition.pollutant_id} />{definition.sources.map((source) => <SummaryRow key={source.source_id} label={source.source_id} value={`${source.emission_rate_g_s.toFixed(4)} g/s · ${source.latitude_deg?.toFixed(5)}, ${source.longitude_deg?.toFixed(5)}`} />)}</article> : <article className="review-card"><header><Factory size={18} /><h2>Fuente puntual</h2><button onClick={() => setStep(1)}>Editar</button></header><SummaryRow label="ID / contaminante" value={`${definition.source.source_id} / ${definition.pollutant_id}`} /><SummaryRow label="Coordenadas" value={definition.source.latitude_deg != null && definition.source.longitude_deg != null ? `${definition.source.latitude_deg.toFixed(6)}, ${definition.source.longitude_deg.toFixed(6)}` : "No informadas"} /><SummaryRow label="Emisión" value={definition.source.emission_rate_g_s.toFixed(4)} unit="g/s" /><SummaryRow label="Altura" value={definition.source.stack_height_m.toFixed(2)} unit="m" /><SummaryRow label="Temperatura" value={definition.source.stack_temperature_k.toFixed(2)} unit="K" /><SummaryRow label="Velocidad / diámetro" value={`${definition.source.exit_velocity_m_s.toFixed(2)} m/s · ${definition.source.stack_diameter_m.toFixed(2)} m`} /></article>}
                  {isMultiSourceHourlyDefinition(definition) ? <>
                    <article className="review-card"><header><Wind size={18} /><h2>Horario multifuente</h2><button onClick={() => setStep(2)}>Editar</button></header><SummaryRow label="Estación" value={definition.meteorology.station === "cordoba-aero" ? "Córdoba Aero · OMM 87344" : "Mendoza Aero · OMM 87418"} /><SummaryRow label="Período" value={definition.meteorology.year} /><SummaryRow label="Grupo AERMOD" value="ALL · aportes combinados" /><SummaryRow label="Procesador" value="AERMET 26135" /><SummaryRow label="Clasificación" value={definition.dispersion_mode === "rural" ? "Rural" : "Urbana"} /></article>
                    <article className="review-card wide"><header><Gauge size={18} /><h2>Red multifuente</h2><button onClick={() => setStep(2)}>Editar</button></header><div className="summary-columns"><SummaryRow label="Terreno" value={definition.terrain.mode === "complex" ? "Complejo · Copernicus GLO-30 + AERMAP" : "Plano"} /><SummaryRow label="Downwash" value="No incluido" /><SummaryRow label="Límite ambiental" value={definition.receptors.ambient_boundary_distance_m} unit="m" /><SummaryRow label="Intervalo" value={`${definition.receptors.search_start_m}–${definition.receptors.search_end_m}`} unit="m" /><SummaryRow label="Resolución radial" value={definition.receptors.search_step_m} unit="m" /><SummaryRow label="Resolución angular" value={definition.receptors.direction_step_deg} unit="°" /></div></article>
                  </> : isHourlyDefinition(definition) ? <>
                    <article className="review-card"><header><Wind size={18} /><h2>Horario observado</h2><button onClick={() => setStep(2)}>Editar</button></header><SummaryRow label="Estación" value={definition.meteorology.station === "cordoba-aero" ? "Córdoba Aero · OMM 87344" : "Mendoza Aero · OMM 87418"} /><SummaryRow label="Período" value={definition.meteorology.year} /><SummaryRow label="Fuentes" value="NOAA ISD + IGRA" /><SummaryRow label="Procesador" value="AERMET 26135" /><SummaryRow label="Clasificación" value={definition.dispersion_mode === "rural" ? "Rural" : "Urbana"} /></article>
                    <article className="review-card wide"><header><Gauge size={18} /><h2>Red horaria</h2><button onClick={() => setStep(2)}>Editar</button></header><div className="summary-columns"><SummaryRow label="Terreno" value={definition.terrain.mode === "complex" ? "Complejo · Copernicus GLO-30" : "Plano"} /><SummaryRow label="Downwash" value={definition.downwash.enabled ? `${definition.downwash.buildings[0].building_id} · ${definition.downwash.buildings[0].height_m} m · BPIPPRM/PRIME` : "No incluido"} /><SummaryRow label="Límite ambiental" value={definition.receptors.ambient_boundary_distance_m} unit="m" /><SummaryRow label="Intervalo" value={`${definition.receptors.search_start_m}–${definition.receptors.search_end_m}`} unit="m" /><SummaryRow label="Resolución radial" value={definition.receptors.search_step_m} unit="m" /><SummaryRow label="Resolución angular" value={definition.receptors.direction_step_deg} unit="°" /></div></article>
                  </> : <>
                    <article className="review-card"><header><Wind size={18} /><h2>Screening</h2><button onClick={() => setStep(2)}>Editar</button></header><SummaryRow label="Clasificación" value={definition.dispersion_mode === "rural" ? "Rural" : "Urbana"} /><SummaryRow label="Temperaturas" value={`${definition.meteorology.minimum_temperature_k}–${definition.meteorology.maximum_temperature_k}`} unit="K" /><SummaryRow label="Albedo / Bowen" value={`${definition.meteorology.albedo} / ${definition.meteorology.bowen_ratio}`} /><SummaryRow label="Rugosidad" value={definition.meteorology.surface_roughness_m} unit="m" /><SummaryRow label="Viento mínimo" value={definition.meteorology.minimum_wind_speed_m_s} unit="m/s" />{definition.meteorology.observations_selection && <SummaryRow label="Observaciones" value={`${definition.meteorology.observations_selection} · ${definition.meteorology.observations_period_start} a ${definition.meteorology.observations_period_end}`} />}</article>
                    <article className="review-card wide"><header><Gauge size={18} /><h2>Red, terreno y edificios</h2><button onClick={() => setStep(2)}>Editar</button></header><div className="summary-columns"><SummaryRow label="Terreno" value={definition.terrain.mode === "complex" ? "Complejo · Copernicus GLO-30" : "Plano"} />{definition.terrain.compare_with_flat && <SummaryRow label="Control de terreno" value="Comparar con terreno plano" />}<SummaryRow label="Downwash" value={definition.downwash.enabled ? `${definition.downwash.buildings[0].building_id} · ${definition.downwash.buildings[0].height_m} m` : "No incluido"} /><SummaryRow label="Límite ambiental" value={definition.receptors.ambient_boundary_distance_m} unit="m" /><SummaryRow label="Intervalo" value={`${definition.receptors.search_start_m}–${definition.receptors.search_end_m}`} unit="m" /><SummaryRow label="Resolución" value={definition.receptors.search_step_m} unit="m" /></div></article>
                  </>}
                  {notices.length > 0 && <div className="alert warning wide"><AlertCircle size={18} /><div>{notices.map((notice) => <p key={notice}>{notice}</p>)}</div></div>}
                  <div className="audit-note wide"><FileCheck2 size={22} /><div><strong>Listo para guardar</strong><p>El backend volverá a validar todos los campos. El escenario quedará inmutable; cualquier cambio posterior se guardará como una copia.</p></div></div>
                </section>
              )}
              <footer className="wizard-footer">
                <button className="secondary" onClick={() => step === 0 ? setWizardOpen(false) : setStep((current) => current - 1)}><ArrowLeft size={17} /> {step === 0 ? "Cancelar" : "Anterior"}</button>
                {step < 3 ? <button className="primary" onClick={next}>Continuar <ArrowRight size={17} /></button> : <button className="primary" disabled={saving} onClick={() => void save()}>{saving ? <LoaderCircle className="spin" size={17} /> : <Check size={17} />} Guardar escenario</button>}
              </footer>
            </>
          )}
        </main>
      </div>
      {credentialsDialog}
    </div>
  );
}
