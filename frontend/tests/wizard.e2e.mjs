import { chromium } from "playwright-core";
import { mkdir, writeFile } from "node:fs/promises";

await mkdir("../build/phase-c-validation", { recursive: true });
await mkdir("../build/phase-d-validation", { recursive: true });

const browser = await chromium.launch({ executablePath: "/usr/bin/chromium", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });

try {
  await page.goto("http://127.0.0.1:5173", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Nuevo proyecto" }).click();
  await page.getByLabel("Nombre del proyecto").fill("Validación interfaz Fase C");
  await page.getByLabel("Responsable").fill("FCA Aire");
  await page.getByLabel("Nombre del escenario").fill("EPA desde navegador");
  await page.getByRole("button", { name: /Continuar/ }).click();

  await page.getByText("Parámetros de la fuente").waitFor();
  await page.getByRole("button", { name: /Continuar/ }).click();

  await page.getByText("Condiciones de screening").waitFor();
  await page.getByRole("button", { name: /Continuar/ }).click();

  await page.getByText("Revisar antes de guardar").waitFor();
  await page.getByRole("button", { name: /Guardar escenario/ }).click();
  await page.getByText("ESCENARIO GUARDADO").waitFor({ timeout: 10000 });
  await page.screenshot({ path: "../build/phase-c-validation/scenario-saved.png", fullPage: true });
  await page.getByRole("button", { name: /Ejecutar ahora/ }).click();
  await page.getByText("RESULTADOS DE SCREENING").waitFor({ timeout: 15000 });
  await page.getByText("1,91323").first().waitFor();
  await page.getByText("1.610").first().waitFor();
  const chartVisible = await page.getByRole("img", { name: "Concentración de una hora por distancia" }).isVisible();
  const mapVisible = await page.getByRole("img", { name: "Mapa conceptual del screening" }).isVisible();
  const downloadCount = await page.getByRole("link", { name: /Descargar/ }).count();
  await page.screenshot({ path: "../build/phase-d-validation/results.png", fullPage: true });

  const response = await fetch("http://127.0.0.1:8000/projects");
  const projects = await response.json();
  const project = projects.find((item) => item.name === "Validación interfaz Fase C");
  if (!project) throw new Error("El proyecto no quedó persistido por la API");
  const scenariosResponse = await fetch(`http://127.0.0.1:8000/projects/${project.id}/scenarios`);
  const scenarios = await scenariosResponse.json();
  const saved = scenarios.find((scenario) => scenario.name === "EPA desde navegador");
  if (!saved) throw new Error("El escenario no quedó persistido por la API");
  const checks = {
    dashboard_loaded: true,
    project_step_completed: true,
    source_step_completed: true,
    screening_step_completed: true,
    review_step_completed: true,
    scenario_persisted_by_api: true,
    canonical_emission_is_1_g_s: saved.definition.source.emission_rate_g_s === 1,
    canonical_stack_height_is_61_m: saved.definition.source.stack_height_m === 61,
  };
  const report = {
    phase: "C — interfaz de carga",
    status: Object.values(checks).every(Boolean) ? "PASS" : "FAIL",
    project_id: project.id,
    scenario_id: saved.id,
    checks,
  };
  await writeFile("../build/phase-c-validation/phase-c-validation.json", `${JSON.stringify(report, null, 2)}\n`);
  if (report.status !== "PASS") throw new Error("Falló la validación de la Fase C");
  const runsResponse = await fetch(`http://127.0.0.1:8000/scenarios/${saved.id}/runs`);
  const runs = await runsResponse.json();
  const completedRun = runs.find((run) => run.status === "completed");
  const phaseDChecks = {
    run_started_from_browser: Boolean(completedRun),
    epa_maximum_visible: true,
    epa_distance_visible: true,
    concentration_chart_visible: chartVisible,
    context_map_visible: mapVisible,
    scaled_periods_visible: await page.getByText("Concentraciones escaladas").isVisible(),
    traceability_visible: await page.getByText("Información de corrida").isVisible(),
    artifacts_downloadable: downloadCount >= 10,
  };
  const phaseDReport = {
    phase: "D — ejecución y visualización de resultados",
    status: Object.values(phaseDChecks).every(Boolean) ? "PASS" : "FAIL",
    scenario_id: saved.id,
    run_id: completedRun?.id,
    actual: {
      maximum_1h_ug_m3: completedRun?.result?.maximum_1h_ug_m3,
      maximum_distance_m: completedRun?.result?.maximum_distance_m,
      curve_points: completedRun?.result?.concentration_by_distance?.length,
      download_links: downloadCount,
    },
    checks: phaseDChecks,
  };
  await writeFile("../build/phase-d-validation/phase-d-validation.json", `${JSON.stringify(phaseDReport, null, 2)}\n`);
  if (phaseDReport.status !== "PASS") throw new Error("Falló la validación de la Fase D");
  console.log("PASS: asistente completo y escenario persistido desde Chromium");
} finally {
  await browser.close();
}
