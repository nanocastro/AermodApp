from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .executables import stage_executable
from .models import Building, PointSource, ScreeningScenario
from .generator import aermod_ascii


PARAMETERS = ("BUILDHGT", "BUILDWID", "BUILDLEN", "XBADJ", "YBADJ")


def generate_bpip_input(scenario: ScreeningScenario) -> str:
    return generate_bpip_input_for_source(
        name=scenario.name,
        source=scenario.source,
        buildings=scenario.downwash.buildings,
        source_base_elevation_m=scenario.receptors.base_elevation_m,
    )


def generate_bpip_input_for_source(
    *, name: str, source: PointSource, buildings: list[Building],
    source_base_elevation_m: float,
) -> str:
    lines = [f"'{aermod_ascii(name)[:70]}'", "'P'", "'METERS'  1.0", "'UTMN', 0.0", str(len(buildings))]
    for building in buildings:
        lines.extend([f"'{building.building_id}' 1 {building.base_elevation_m:.3f}", f"{len(building.vertices)} {building.height_m:.3f}"])
        lines.extend(f"{vertex.east_m:.3f} {vertex.north_m:.3f}" for vertex in building.vertices)
    lines.extend(["1", f"'{source.source_id}' {source_base_elevation_m:.3f} {source.stack_height_m:.3f} 0.0 0.0", ""])
    return "\n".join(lines)


def run_bpipprm(scenario: ScreeningScenario, directory: Path, executable: Path) -> dict[str, list[float]]:
    return run_bpipprm_for_source(
        name=scenario.name,
        source=scenario.source,
        buildings=scenario.downwash.buildings,
        source_base_elevation_m=scenario.receptors.base_elevation_m,
        directory=directory,
        executable=executable,
    )


def run_bpipprm_for_source(
    *, name: str, source: PointSource, buildings: list[Building],
    source_base_elevation_m: float, directory: Path, executable: Path,
) -> dict[str, list[float]]:
    (directory / "building.inp").write_text(
        generate_bpip_input_for_source(
            name=name, source=source, buildings=buildings,
            source_base_elevation_m=source_base_elevation_m,
        ),
        encoding="ascii",
    )
    staged_executable = stage_executable(executable, directory)
    completed = subprocess.run(
        [str(staged_executable), "building.inp", "building.out", "building.sum"],
        cwd=directory, capture_output=True, text=True, timeout=120,
    )
    (directory / "bpipprm.stdout").write_text(completed.stdout + completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError("BPIPPRM no termino correctamente")
    values = {name: [] for name in PARAMETERS}
    for line in (directory / "building.out").read_text(encoding="latin-1").splitlines():
        match = re.match(r"\s*SO\s+(BUILDHGT|BUILDWID|BUILDLEN|XBADJ|YBADJ)\s+\S+\s+(.+)", line)
        if match:
            values[match.group(1)].extend(float(value) for value in match.group(2).split())
    if any(len(item) != 36 for item in values.values()):
        raise RuntimeError("BPIPPRM no genero 36 valores PRIME por parametro")
    return values


def building_parameter_lines(source_id: str, values: dict[str, list[float]]) -> list[str]:
    lines: list[str] = []
    for name in PARAMETERS:
        chunks = [values[name][index:index + 6] for index in range(0, 36, 6)]
        for chunk in chunks:
            lines.append(f"   {name:<8} {source_id} " + " ".join(f"{value:.2f}" for value in chunk))
    return lines
