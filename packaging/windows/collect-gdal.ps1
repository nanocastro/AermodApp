$ErrorActionPreference = "Stop"
$Root = (Resolve-Path "$PSScriptRoot\..\..").Path
$Runtime = Join-Path $Root "packaging\windows\runtime\gdal"
$CondaLibrary = Join-Path $env:CONDA_PREFIX "Library"

New-Item -ItemType Directory -Force (Join-Path $Runtime "bin") | Out-Null
New-Item -ItemType Directory -Force (Join-Path $Runtime "share") | Out-Null
Copy-Item (Join-Path $CondaLibrary "bin\*.dll") (Join-Path $Runtime "bin")
Copy-Item (Join-Path $CondaLibrary "bin\gdal*.exe") (Join-Path $Runtime "bin")
Copy-Item -Recurse -Force (Join-Path $CondaLibrary "share\gdal") (Join-Path $Runtime "share\gdal")
Copy-Item -Recurse -Force (Join-Path $CondaLibrary "share\proj") (Join-Path $Runtime "share\proj")
