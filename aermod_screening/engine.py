from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .executables import stage_executable
from .generator import generate_aermod_input, generate_makemet_prompts
from .models import ScreeningResult, ScreeningScenario
from .parser import parse_result


class ScreeningEngine:
    def __init__(self, *, aermod_executable: Path, makemet_executable: Path) -> None:
        self.aermod_executable = aermod_executable.resolve()
        self.makemet_executable = makemet_executable.resolve()
        for executable in (self.aermod_executable, self.makemet_executable):
            if not executable.is_file():
                raise FileNotFoundError(executable)

    def run(self, scenario: ScreeningScenario, run_directory: Path) -> ScreeningResult:
        run_directory = run_directory.resolve()
        if run_directory.exists() and any(run_directory.iterdir()):
            raise FileExistsError(f"El directorio de corrida no está vacío: {run_directory}")
        run_directory.mkdir(parents=True, exist_ok=True)

        (run_directory / "scenario.json").write_text(
            scenario.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        (run_directory / "prompts.inp").write_text(
            generate_makemet_prompts(scenario), encoding="ascii"
        )
        (run_directory / "aermod.inp").write_text(
            generate_aermod_input(scenario), encoding="ascii"
        )
        aermod = stage_executable(self.aermod_executable, run_directory)
        makemet = stage_executable(self.makemet_executable, run_directory)

        with (run_directory / "prompts.inp").open("r", encoding="ascii") as input_stream, (
            run_directory / "makemet.stdout"
        ).open("w", encoding="utf-8") as output_stream:
            subprocess.run(
                [str(makemet)],
                cwd=run_directory,
                stdin=input_stream,
                stdout=output_stream,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=120,
            )
        with (run_directory / "aermod.stdout").open("w", encoding="utf-8") as output_stream:
            subprocess.run(
                [str(aermod)],
                cwd=run_directory,
                stdout=output_stream,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=300,
            )

        result = parse_result(run_directory)
        (run_directory / "result.json").write_text(
            json.dumps(result.model_dump(), indent=2) + "\n", encoding="utf-8"
        )
        return result
