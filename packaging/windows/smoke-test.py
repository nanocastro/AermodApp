from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path


BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"
ROOT = Path(__file__).resolve().parents[2]


def request(method: str, path: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode() if payload is not None else None
    call = urllib.request.Request(
        f"{BASE_URL}{path}", data=body, method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(call, timeout=10) as response:
        return json.load(response)


health = request("GET", "/health")
for engine in ("aermod", "makemet", "aermap", "bpipprm"):
    if not health[f"{engine}_available"]:
        raise RuntimeError(f"El paquete no contiene {engine}")

project = request("POST", "/projects", {
    "name": "Smoke test Windows", "description": "Validación del paquete",
})
definition = json.loads(
    (ROOT / "examples" / "epa_point_flat_nodw.json").read_text(encoding="utf-8")
)
scenario = request("POST", f"/projects/{project['id']}/scenarios", {
    "name": "EPA flat smoke", "definition": definition,
})
run = request("POST", f"/scenarios/{scenario['id']}/runs")
for _ in range(120):
    run = request("GET", f"/runs/{run['id']}")
    if run["status"] in {"completed", "failed"}:
        break
    time.sleep(0.5)
if run["status"] != "completed":
    raise RuntimeError(f"La corrida portable falló: {run.get('error')}")
if abs(run["result"]["maximum_1h_ug_m3"] - 1.91323) > 0.00001:
    raise RuntimeError("La corrida portable no reprodujo el máximo EPA")
print("Corrida EPA portable completada correctamente")
