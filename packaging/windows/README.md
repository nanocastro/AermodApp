# Paquete portable para Windows

El workflow `Windows portable package` compila los cuatro motores con las
fuentes oficiales EPA, compila el frontend y genera
`AERMOD-Screening-Windows-x64.zip`. Antes de comprimirlo, inicia el ejecutable
recién construido y comprueba que el endpoint `/health` responda correctamente.

Al descomprimir, ejecutar `AERMOD-Screening.exe`. La consola debe permanecer
abierta mientras se usa la aplicación. Los proyectos, resultados, DEM y caché
se guardan en `%LOCALAPPDATA%\AERMOD Screening`; las credenciales se guardan en
Windows Credential Manager y nunca se incluyen en el ZIP.

La distribución es portable y no requiere instalar Python, Node.js ni GDAL.
Antes de distribuir una versión definitiva se debe ejecutar el caso EPA desde
una máquina Windows limpia y firmar digitalmente el ejecutable para reducir las
advertencias de SmartScreen.
