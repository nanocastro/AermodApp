# Arquitectura y operación

Este documento reúne los detalles técnicos que acompañan la presentación general
de [AERMOD Argentina](../README.md): componentes, flujos de ejecución,
persistencia, configuración, comandos y empaquetado.

## Componentes

```text
frontend/                       React + TypeScript + Vite + Leaflet
    src/App.tsx                 proyectos y asistente de escenarios
    src/ResultsView.tsx         resultados, mapas y trazabilidad
    src/api.ts                  cliente HTTP
    src/types.ts                contratos TypeScript

aermod_api/                     FastAPI, SQLite y orquestación
    app.py                      rutas y composición
    config.py                   configuración y carga de .env
    database.py                 persistencia
    environment_jobs.py        trabajos ambientales y progreso
    service.py                  corridas y preparación AERMAP
    stations.py                 observaciones horarias SMN
    surface.py                  MODIS, ERA5-Land y WorldCover

aermod_screening/               screening de fuente única
    models.py                   contrato Pydantic
    generator.py                entradas MAKEMET/AERMOD
    engine.py                   caso plano sin downwash
    complex_engine.py           terreno y envolvente de 36 sectores
    downwash.py                 geometría e integración BPIPPRM
    downwash_engine.py          comparación con/sin PRIME
    terrain.py                  DEM, UTM y entradas AERMAP

aermod_hourly/                  fuente única cronológica
    models.py                   contrato horario
    generator.py                entrada AERMOD y parámetros PRIME
    engine.py                   ejecución, parser y comparaciones
    aermet.py                   generación AERMET, QA y manifiestos
    noaa.py                     descarga y normalización NOAA
    stations.py                 estaciones y parámetros estacionales

aermod_multisource/             horario de 2 a 100 fuentes
    models.py                   contrato multifuente
    geometry.py                 sistema relativo compartido
    generator.py                fuentes y SRCGROUP ALL
    engine.py                   ejecución y consolidación
    terrain.py                  dominio UTM y AERMAP compartido

scripts/                        preparación y regresiones reproducibles
examples/                       sólo escenarios de validación oficial EPA
tests/                          pruebas backend
packaging/windows/              distribución portable
bin/                            ejecutables locales
data/                           SQLite, corridas, DEM y caché; ignorado
build/                          compilaciones y validaciones; ignorado
```

Las rutas de API se mantienen delgadas. La validación reside en los modelos y la
lógica científica en servicios, generadores y motores específicos de cada
modalidad.

## Flujo general

```text
Navegador
  → FastAPI
  → validación Pydantic
  → persistencia del escenario canónico
  → preparación requerida
      ├─ MAKEMET
      ├─ AERMET + NOAA ISD/IGRA
      ├─ AERMAP + Copernicus DEM
      └─ BPIPPRM + edificios
  → AERMOD
  → parser y controles
  → SQLite + artefactos + hashes
  → interfaz y exportación
```

Cada modificación se guarda como un escenario nuevo. Las corridas anteriores,
incluidos sus errores, se conservan localmente para auditoría y están excluidas
del repositorio.

## Flujos por modalidad

### Screening

1. Se valida una fuente puntual y la meteorología sintética.
2. En terreno complejo se descarga/prepara el DEM y AERMAP asigna cotas.
3. Si hay edificios, BPIPPRM genera los parámetros PRIME.
4. MAKEMET genera la matriz de condiciones meteorológicas.
5. AERMOD evalúa una dirección en plano o 36 sectores en terreno complejo.
6. Con downwash se agrega un control equivalente sin PRIME.
7. El parser consolida máximos, perfiles, comparaciones y artefactos.

En screening complejo, cada sector mantiene receptores sobre el rayo a
sotavento. No debe sustituirse por una red omnidireccional.

### Horario de fuente única

1. El escenario selecciona estación y año y consume `.SFC/.PFL` preparados.
2. La red receptora radial es omnidireccional.
3. El terreno complejo se procesa una vez con AERMAP.
4. Con downwash, BPIPPRM genera 36 arreglos PRIME.
5. AERMOD procesa la secuencia real con `AVERTIME 1 3 8 24 ANNUAL`, sin
   `MODELOPT SCREEN`.
6. Con PRIME se repite la misma corrida sin downwash para comparar períodos.
7. Se conservan máximos espaciales, hora del máximo global, condición
   meteorológica, contornos, entradas, salidas y hashes.

### Horario multifuente

1. Las fuentes se proyectan a un sistema UTM relativo común.
2. Se construye una malla receptora compartida.
3. En terreno complejo, AERMAP procesa fuentes y receptores en un único dominio.
4. AERMOD usa `SRCGROUP ALL` y calcula la concentración combinada.
5. El resultado conserva posiciones, cotas, máximos de cinco períodos y
   superficie de concentración.

No se generan parámetros PRIME multifuente hasta validar la asociación entre
edificios, chimeneas y arreglos por fuente.

## Servicios de datos

### Terreno

Copernicus GLO-30 se descarga y almacena en caché. El dominio se transforma a la
zona UTM correspondiente y AERMAP 24142 genera elevación y altura crítica de
receptores. Los archivos DEM, entradas, salidas y hashes quedan asociados al
escenario.

### Superficie

Los trabajos ambientales persistentes consultan AppEEARS/MODIS, ERA5-Land y
WorldCover. Informan etapa, avance, cobertura, faltantes, advertencias y errores;
pueden reintentarse sin perder el registro anterior. El desarrollo científico de
estos parámetros está en
[Parámetros de superficie](../PARAMETROS_SUPERFICIE_AERMOD.md).

### Estaciones

El servicio SMN elige la red regional más cercana según las coordenadas:
Mendoza Aero/Observatorio o Córdoba Aero/Observatorio. Entrega cobertura,
distancia, temperatura y percentiles de viento por estación, además de un
promedio combinado ponderado. Esta caracterización se guarda con su período y
procedencia.

La meteorología cronológica usa por separado los conjuntos NOAA/AERMET de
Córdoba Aero y Mendoza Aero. `scripts/prepare_hourly_meteorology.py` descarga
NOAA ISD/IGRA, construye la entrada de AERMET, ejecuta el preprocesador y registra
QA, hashes y manifiestos bajo `data/hourly/`.

## Persistencia y artefactos

SQLite guarda proyectos, escenarios, corridas y trabajos ambientales. Los
artefactos científicos se escriben bajo `data/runs/` y pueden incluir:

- escenario canónico y resultado JSON;
- entradas y salidas AERMOD;
- `.SFC/.PFL` utilizados;
- DEM y resultados AERMAP;
- entrada/salida BPIPPRM y parámetros PRIME;
- comparaciones de terreno o downwash;
- registros de consola, versiones y hashes SHA-256.

`data/` y `build/` son generados e ignorados: no deben editarse ni tratarse como
fuente de verdad del código.

## Mapas y exportación

Leaflet permite alternar calles, relieve OpenTopoMap, WorldCover,
concentraciones, máximos, fuentes, edificios, parámetros de superficie y
estaciones. Los overlays son transparentes para preservar el mapa base. El mapa
visible y el perfil concentración–distancia se exportan como PNG independientes.

## Configuración y secretos

`aermod_api/config.py` carga `.env` desde la raíz mediante `python-dotenv`.
Variables principales:

```text
AERMOD_EXECUTABLE
AERMET_EXECUTABLE
MAKEMET_EXECUTABLE
AERMAP_EXECUTABLE
BPIPPRM_EXECUTABLE
AERMOD_DATABASE
AERMOD_RUNS_DIR
AERMOD_HOURLY_DIR
AERMOD_TERRAIN_DIR
AERMOD_SURFACE_DIR
EARTHDATA_USERNAME
EARTHDATA_PASSWORD
CDSAPI_KEY
```

`.env` está ignorado y `.env.example` sólo contiene campos vacíos. CDS requiere
que el titular acepte la licencia ERA5-Land. Los secretos nunca deben mostrarse,
registrarse ni incluirse en artefactos. En Windows portable se guardan en
Credential Manager.

## Desarrollo local

Requisitos: Python 3.11+, Node.js/npm y los ejecutables preparados en `bin/`.

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cd frontend
npm install
cd ..
```

Backend:

```bash
.venv/bin/uvicorn aermod_api.app:app --host 127.0.0.1 --port 8000 --reload
```

Frontend:

```bash
cd frontend
npm run dev -- --host 127.0.0.1
```

La aplicación queda en <http://127.0.0.1:5173>, la API en
<http://127.0.0.1:8000> y OpenAPI en <http://127.0.0.1:8000/docs>.

## Ejecuciones reproducibles

Meteorología AERMET:

```bash
.venv/bin/python scripts/prepare_hourly_meteorology.py \
  --station cordoba-aero --year 2024
```

Fuente única horaria con un escenario local ignorado por Git:

```bash
.venv/bin/python scripts/run_hourly_aermod.py \
  data/scenarios/hourly.json \
  --output build/hourly-local
```

Un caso con terreno complejo requiere además `--terrain-directory` con un
dominio AERMAP preparado bajo `data/terrain/`.

Multifuente con un escenario local ignorado por Git:

```bash
.venv/bin/python scripts/run_multisource_aermod.py \
  data/scenarios/multisource.json \
  --output build/multisource-local
```

Regresión oficial AERMET `EX01`:

```bash
.venv/bin/python scripts/validate_epa_aermet_case.py
```

## Pruebas

```bash
.venv/bin/python -m unittest discover -s tests -v
cd frontend
npm test -- --run
npm run build
```

Los cambios científicos deben ejecutar además la regresión real correspondiente
y registrar versiones, resultados y decisiones en la bitácora local ignorada por
Git. Sólo las validaciones oficiales EPA se incorporan al repositorio público.

## Windows portable

El workflow `.github/workflows/windows-package.yml`:

1. descarga fuentes oficiales verificadas por SHA-256;
2. compila AERMOD 26135, MAKEMET 16216 y AERMAP 24142;
3. incorpora BPIPPRM 04274 y GDAL;
4. compila el frontend y crea `AERMOD-Screening.exe` con PyInstaller;
5. verifica `/health` y ejecuta un caso EPA;
6. publica `AERMOD-Screening-Windows-x64.zip` como artefacto.

El paquete guarda SQLite, DEM, caché y resultados bajo
`%LOCALAPPDATA%\AERMOD Screening`. La consola permanece abierta mientras se usa
la aplicación. La distribución portable actual está centrada en screening; para
habilitar horario debe incorporar AERMET y los `.SFC/.PFL` validados.

El procedimiento de prueba limpia está en
[Paquete portable para Windows](../packaging/windows/README.md).

## Decisiones y límites vigentes

- Las semánticas de screening, horario y multifuente permanecen separadas.
- Los promedios horarios son cálculos directos de AERMOD, no factores de
  conversión de screening.
- La altura física de chimeneas/edificios no se confunde con su elevación base.
- El texto destinado a ejecutables Fortran se normaliza a ASCII.
- No se afirma compatibilidad MMIF con productos WRF superficiales.
- Los resultados argentinos no son regulatorios sin revisión externa.

El plan de trabajo, la bitácora y las guías de continuidad que contienen casos
locales se mantienen fuera del repositorio público mediante `.gitignore`.

## Fuentes y documentación externa

- [EPA — AERMOD Modeling System](https://www.epa.gov/scram/air-quality-dispersion-modeling-preferred-and-recommended-models)
- [EPA — AERMET y procesadores meteorológicos](https://www.epa.gov/scram/meteorological-processors-and-accessory-programs#aermet)
- [NASA AppEEARS](https://appeears.earthdatacloud.nasa.gov/)
- [MODIS MCD43A3](https://lpdaac.usgs.gov/products/mcd43a3v061/)
- [ERA5-Land](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land)
- [ESA WorldCover](https://esa-worldcover.org/en/data-access)
- [SMN — Datos meteorológicos horarios](https://www.datos.gob.ar/dataset/smn-datos-meteorologicos-horarios/archivo/smn_2.1)
- [Copernicus DEM](https://registry.opendata.aws/copernicus-dem/)
- [OpenStreetMap](https://www.openstreetmap.org/copyright)
- [OpenTopoMap](https://www.opentopomap.org/about)
