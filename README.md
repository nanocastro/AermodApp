# AERMOD Argentina

Aplicación web local para configurar, preprocesar, ejecutar y visualizar estudios
de dispersión atmosférica con fuentes puntuales. Integra los ejecutables oficiales
de AERMOD y sus preprocesadores, conserva los archivos de cada corrida y evita la
edición manual de entradas Fortran.

> **Estado:** prototipo funcional con validaciones técnicas contra casos oficiales
> de EPA. Los resultados de Mendoza y Córdoba todavía requieren revisión
> científica externa; no deben presentarse como resultados
> regulatorios definitivos.

![Flujo visual de la aplicación: proyectos, meteorología horaria y validación EPA](docs/images/aermod-workflow-public.png)

## Qué permite hacer

La aplicación mantiene tres modalidades independientes:

| Modalidad | Fuentes | Meteorología | Terreno | Downwash |
|---|---:|---|---|---|
| `screening` | 1 | Sintética conservadora con MAKEMET | Plano o Copernicus GLO-30 + AERMAP | Sí, BPIPPRM/PRIME |
| `hourly` | 1 | Cronológica 2024, NOAA ISD + IGRA procesada con AERMET | Plano o Copernicus GLO-30 + AERMAP | Sí, con control equivalente sin PRIME |
| `multi_source_hourly` | 2–100 | Cronológica 2024, NOAA ISD + IGRA procesada con AERMET | Plano o complejo, con dominio compartido | No implementado aún |

En las tres modalidades se dispone de:

- proyectos, escenarios inmutables, duplicación y ejecuciones históricas;
- fuentes rurales o urbanas y coordenadas geográficas WGS84;
- validación estricta de unidades y parámetros antes de ejecutar;
- seguimiento de progreso y persistencia de resultados y errores;
- mapas con calles, relieve, cobertura del suelo, fuentes, edificios y
  concentraciones;
- descarga de entradas, salidas, registros, resultados y hashes SHA-256;
- exportación del mapa y del perfil de concentración como PNG.

El detalle de componentes, flujos y estructura del repositorio está en
[Arquitectura y operación](docs/ARCHITECTURE.md).

## Parámetros utilizados

### Fuente y dominio

- identificador y contaminante;
- emisión en `g/s`;
- altura y diámetro interior de chimenea en `m`;
- temperatura de salida en `K` y velocidad en `m/s`;
- latitud y longitud WGS84;
- clasificación rural o urbana —esta última requiere población—;
- límite ambiental, intervalo, paso y altura de receptores;
- terreno plano o elevaciones/alturas críticas generadas por AERMAP;
- geometría de edificios y parámetros PRIME cuando se activa downwash.

Las unidades alternativas de la interfaz se convierten al contrato canónico
antes de persistir el escenario.

### Screening

MAKEMET genera una matriz meteorológica sintética de peor caso a partir de:

- temperatura mínima y máxima;
- velocidad mínima, altura de anemómetro y dirección del viento;
- albedo, razón de Bowen y longitud de rugosidad;
- ajuste opcional de velocidad de fricción mínima.

La aplicación puede estimar parámetros locales usando los dos últimos meses
calendario completos:

| Parámetro | Fuente | Tratamiento actual |
|---|---|---|
| Albedo | MODIS `MCD43A3.061/Albedo_WSA_shortwave` vía AppEEARS | QA obligatorio `≤ 1`; exige cobertura mayor que 50 % |
| Razón de Bowen | ERA5-Land | `abs(sum(sshf) / sum(slhf))` para pares válidos; exige cobertura mayor que 50 % |
| Rugosidad | ESA WorldCover 2021 | 36 sectores entre 100 y 1.000 m con correspondencia estacional EPA/ECMWF |

En terreno complejo, las rugosidades se agrupan en hasta cinco candidatos que
conservan los extremos. AERMOD evalúa cada candidato y selecciona el que produce
la mayor concentración. Los valores siguen siendo editables y deben revisarse
antes de adoptarlos.

La metodología, efectos físicos y precauciones están desarrollados en
[Parámetros de superficie en AERMOD](PARAMETROS_SUPERFICIE_AERMOD.md).

### Meteorología horaria

Los escenarios horarios consumen directamente archivos `.SFC/.PFL` 2024
preparados con AERMET 26135:

| Conjunto | Superficie | Perfil vertical | Horas utilizables |
|---|---|---|---:|
| Córdoba Aero | NOAA ISD `873440-99999` | NOAA IGRA `ARM00087344` | 8.095/8.784 — 92,2 % |
| Mendoza Aero | NOAA ISD `874180-99999` | NOAA IGRA `ARM00087418` | 5.932/8.784 — 67,5 % |

Las calmas y faltantes se conservan como fueron informados; no se rellenan horas
ni se aplican factores empíricos de screening. AERMOD calcula directamente los
máximos de 1, 3, 8 y 24 horas y anual.

Las observaciones regionales del SMN para Mendoza Aero/Observatorio y Córdoba
Aero/Observatorio se usan como apoyo para caracterizar escenarios de screening;
no se mezclan con la secuencia AERMET por conveniencia.

## Cómo interpretar los resultados

- En **screening complejo**, el mapa es una envolvente conservadora de 36
  direcciones sintéticas sobre el rayo a sotavento, no una serie cronológica.
- En **modo horario**, los contornos representan el máximo de 1 hora alcanzado
  en cada receptor durante el año. Esos máximos pueden ocurrir en horas distintas
  y no forman una instantánea simultánea.
- En **multifuente**, los máximos y contornos corresponden a la concentración
  combinada del grupo AERMOD `ALL`.
- Con **downwash horario de fuente única**, se ejecuta además un control con la
  misma meteorología, terreno y receptores, pero sin PRIME.
- En terreno complejo con edificios, la implementación actual aproxima la cota
  base de cada edificio con la cota AERMAP de la chimenea y registra la decisión
  en `building-base-elevations.json`.

## Validaciones realizadas

| Caso | Resultado reproducido | Estado |
|---|---:|---|
| EPA `POINT_FLAT_NODW` | 1,91323 µg/m³ a 1.610 m | PASS |
| EPA `POINT_TERR_NODW` | 1,914 µg/m³ a 1.620 m, 110° | PASS |
| EPA `POINT_FLAT_DW` | 12,19 µg/m³ a 150 m, 250° | PASS |
| EPA `POINT_TERR_DW` | 12,17 µg/m³ a 150 m, 270° | PASS |
| AERMET 26135 `EX01` | `.SFC/.PFL` idénticos tras normalizar CRLF/LF | PASS |

Las regresiones ejecutan AERMOD, AERMET, AERMAP y BPIPPRM reales cuando el caso
lo requiere. Al 29 de septiembre de 2026 pasan **71 pruebas backend**, **10 pruebas
frontend** y el build TypeScript/Vite.

Los escenarios, resultados y valores de casos locales no forman parte del
repositorio público. Sólo se publican entradas y resultados correspondientes a
validaciones oficiales EPA.

## Puesta en marcha

Requiere Python 3.11+, Node.js/npm y los ejecutables preparados en `bin/`.

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cd frontend && npm install && cd ..
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

- Aplicación: <http://127.0.0.1:5173>
- API: <http://127.0.0.1:8000>
- OpenAPI: <http://127.0.0.1:8000/docs>

La configuración completa, preparación de meteorología, casos reproducibles y
pruebas están en [Arquitectura y operación](docs/ARCHITECTURE.md).

### Windows portable

El workflow manual genera `AERMOD-Screening-Windows-x64.zip`. El paquete se
descomprime y ejecuta con `AERMOD-Screening.exe`, sin instalar Python, Node.js o
GDAL. La versión portable publicada actualmente está preparada para screening;
incorporar AERMET y los conjuntos horarios al ZIP continúa pendiente.

Consultar [Prueba del paquete Windows](packaging/windows/README.md) antes de
distribuirlo en una máquina limpia.

## Alcance y pendientes

Está implementado el flujo técnico completo descrito arriba, pero permanecen
pendientes:

- revisión científica de albedo, Bowen, rugosidad, cobertura y estaciones;
- aprobación externa de los pilotos de Mendoza y Córdoba;
- revisión de la aproximación de cota base de edificios en terreno complejo;
- contribuciones separadas por fuente e importación CSV;
- downwash multifuente;
- firma digital y ampliación horaria del paquete Windows.

WRF/MMIF permanece fuera de alcance hasta disponer de archivos WRF nativos con
las variables tridimensionales requeridas.

## Documentación

- [Arquitectura, operación y comandos](docs/ARCHITECTURE.md)
- [Parámetros de superficie](PARAMETROS_SUPERFICIE_AERMOD.md)
- [Paquete portable para Windows](packaging/windows/README.md)
- [Validación oficial EPA reproducible](examples/epa_point_flat_nodw.json)
- [Política de credenciales y datos privados](SECURITY.md)

## Licencia

El código fuente se distribuye bajo la [licencia MIT](LICENSE). Los ejecutables,
datos y documentos de terceros conservan sus propias condiciones de uso y no se
incluyen en el repositorio salvo indicación expresa.

## Referencias principales

- [EPA — AERMOD Modeling System](https://www.epa.gov/scram/air-quality-dispersion-modeling-preferred-and-recommended-models)
- [EPA — Screening Models/AERSCREEN](https://www.epa.gov/scram/air-quality-dispersion-modeling-screening-models#aerscreen)
- [Guía de AERMOD](https://gaftp.epa.gov/aqmg/SCRAM/models/preferred/aermod/aermod_userguide.pdf)
- [Guía de AERSURFACE](https://gaftp.epa.gov/aqmg/SCRAM/models/related/aersurface/aersurface_ug_v24142.pdf)
