from pathlib import Path

root = Path(SPECPATH).parents[1]
runtime = root / "packaging" / "windows" / "runtime"

datas = [
    (str(root / "frontend" / "dist"), "frontend"),
    (str(runtime / "bin"), "model-bin"),
    (str(runtime / "gdal" / "bin"), "gdal-bin"),
    (str(runtime / "gdal" / "share" / "gdal"), "gdal-data"),
    (str(runtime / "gdal" / "share" / "proj"), "proj-data"),
]

analysis = Analysis(
    [str(root / "packaging" / "windows" / "launcher.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "aermod_api.app",
        "aermod_screening",
        "keyring.backends.Windows",
        "netCDF4.utils",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="AERMOD-Screening",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    name="AERMOD-Screening",
)
