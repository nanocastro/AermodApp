import type { Artifact, CredentialStatus, EnvironmentJob, Project, Run, Scenario, ScenarioDefinition, StationEstimate, SurfaceEstimate, TerrainPreparation } from "./types";

const API_BASE = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "http://127.0.0.1:8000" : window.location.origin);

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options?.headers ?? {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "Error inesperado" }));
    const detail = typeof body.detail === "string" ? body.detail : "Los datos no pasaron la validación.";
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export const api = {
  baseUrl: API_BASE,
  credentialStatus: () => request<CredentialStatus>("/credentials"),
  saveCredentials: (payload: { earthdata_username: string; earthdata_password: string; cdsapi_key: string }) =>
    request<CredentialStatus>("/credentials", { method: "POST", body: JSON.stringify(payload) }),
  listProjects: () => request<Project[]>("/projects"),
  createProject: (payload: Pick<Project, "name" | "description" | "responsible">) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify(payload) }),
  listScenarios: (projectId: string) => request<Scenario[]>(`/projects/${projectId}/scenarios`),
  createScenario: (projectId: string, name: string, definition: ScenarioDefinition) =>
    request<Scenario>(`/projects/${projectId}/scenarios`, {
      method: "POST",
      body: JSON.stringify({ name, definition }),
    }),
  createRun: (scenarioId: string) =>
    request<Run>(`/scenarios/${scenarioId}/runs`, { method: "POST" }),
  prepareTerrain: (scenarioId: string) =>
    request<TerrainPreparation>(`/scenarios/${scenarioId}/terrain/prepare`, { method: "POST" }),
  estimateSurface: (latitudeDeg: number, longitudeDeg: number) =>
    request<SurfaceEstimate>("/surface/estimate", { method: "POST", body: JSON.stringify({ latitude_deg: latitudeDeg, longitude_deg: longitudeDeg }) }),
  estimateStations: (latitudeDeg: number, longitudeDeg: number) =>
    request<StationEstimate>("/meteorology/stations/estimate", { method: "POST", body: JSON.stringify({ latitude_deg: latitudeDeg, longitude_deg: longitudeDeg }) }),
  createEnvironmentJob: (kind: EnvironmentJob["kind"], latitudeDeg: number, longitudeDeg: number) =>
    request<EnvironmentJob>("/environment/jobs", { method: "POST", body: JSON.stringify({ kind, latitude_deg: latitudeDeg, longitude_deg: longitudeDeg }) }),
  getEnvironmentJob: (jobId: string) => request<EnvironmentJob>(`/environment/jobs/${jobId}`),
  retryEnvironmentJob: (jobId: string) => request<EnvironmentJob>(`/environment/jobs/${jobId}/retry`, { method: "POST" }),
  listRuns: (scenarioId: string) => request<Run[]>(`/scenarios/${scenarioId}/runs`),
  getRun: (runId: string) => request<Run>(`/runs/${runId}`),
  repeatRun: (runId: string) => request<Run>(`/runs/${runId}/repeat`, { method: "POST" }),
  listArtifacts: (runId: string) => request<Artifact[]>(`/runs/${runId}/artifacts`),
  artifactUrl: (runId: string, artifactId: string) =>
    `${API_BASE}/runs/${runId}/artifacts/${artifactId}`,
};
