# Credenciales y datos privados

## Qué puede publicarse

- código fuente y documentación general;
- contratos, pruebas unitarias y scripts sin datos de usuarios;
- escenarios, entradas y resultados de validaciones oficiales EPA bajo
  `examples/` o fixtures identificados explícitamente como EPA;
- capturas saneadas que no muestren proyectos, responsables, UUID ni resultados
  de estudios locales.

## Qué permanece local

- `.env` y archivos de credenciales;
- bases SQLite;
- proyectos, escenarios, corridas y exportaciones;
- meteorología `.SFC/.PFL` y descargas de proveedores;
- DEM, rásteres y archivos de trabajo AERMOD/AERMET/AERMAP/BPIPPRM;
- plan, bitácora y guía de continuidad que documenten casos locales;
- capturas fuente de la interfaz con datos reales.

Estas categorías están cubiertas por [`.gitignore`](.gitignore). En
`examples/`, la regla de excepción permite únicamente archivos `epa_*.json`.

## Manejo de secretos

Las credenciales se leen desde variables de entorno o desde el almacenamiento
local configurado por la aplicación. `.env.example` contiene sólo nombres de
variables y campos secretos vacíos. En Windows portable se usa Credential
Manager.

Nunca incluir valores reales en código, documentación, capturas, logs, fixtures,
issues o artefactos de CI. Si un secreto llega a Git, ignorar el archivo después
no lo elimina del historial: primero debe revocarse o rotarse y luego sanearse el
historial remoto de manera coordinada.

## Control antes de publicar

```bash
git status --short --ignored
git ls-files
git log --all --name-only
```

Antes de cada publicación se debe comprobar que:

1. `.env`, `data/`, `build/`, escenarios y corridas figuren como ignorados;
2. sólo existan ejemplos EPA en el conjunto publicable;
3. las capturas no contengan nombres, UUID, rutas o resultados privados;
4. no haya tokens, claves privadas, contraseñas ni URLs con autenticación
   embebida en el árbol actual o en el historial.
