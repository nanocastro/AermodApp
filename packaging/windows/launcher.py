from __future__ import annotations

import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path


def resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


def available_port(preferred: int = 8765) -> int:
    for port in range(preferred, preferred + 20):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("No se encontró un puerto local disponible")


def configure_environment() -> tuple[int, str]:
    resources = resource_root()
    user_root = Path(os.getenv("LOCALAPPDATA", Path.home())) / "AERMOD Screening"
    user_root.mkdir(parents=True, exist_ok=True)
    model_bin = resources / "model-bin"
    gdal_bin = resources / "gdal-bin"
    os.environ.update({
        "AERMOD_DATABASE": str(user_root / "aermod.sqlite3"),
        "AERMOD_RUNS_DIR": str(user_root / "runs"),
        "AERMOD_TERRAIN_DIR": str(user_root / "terrain"),
        "AERMOD_SURFACE_DIR": str(user_root / "surface"),
        "AERMOD_CREDENTIALS_FILE": str(user_root / ".credentials"),
        "AERMOD_FRONTEND_DIR": str(resources / "frontend"),
        "AERMOD_EXECUTABLE": str(model_bin / "aermod.exe"),
        "MAKEMET_EXECUTABLE": str(model_bin / "makemet.exe"),
        "AERMAP_EXECUTABLE": str(model_bin / "aermap.exe"),
        "BPIPPRM_EXECUTABLE": str(model_bin / "bpipprm.exe"),
        "GDAL_DATA": str(resources / "gdal-data"),
        "PROJ_LIB": str(resources / "proj-data"),
        "PATH": str(gdal_bin) + os.pathsep + os.environ.get("PATH", ""),
    })
    port = available_port()
    return port, f"http://127.0.0.1:{port}"


def open_when_ready(url: str) -> None:
    for _ in range(80):
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=1):
                webbrowser.open(url)
                return
        except Exception:
            time.sleep(0.25)


def main() -> None:
    port, url = configure_environment()
    threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()
    print(f"AERMOD Screening está disponible en {url}")
    print("Cerrá esta ventana para detener la aplicación.")
    import uvicorn
    from aermod_api.app import app

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
