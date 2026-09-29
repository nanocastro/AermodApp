from __future__ import annotations

import shutil
from pathlib import Path


def stage_executable(source: Path, directory: Path) -> Path:
    """Copy an engine into a run directory without dropping its platform suffix."""
    source = source.resolve()
    target = directory.resolve() / source.name
    shutil.copy2(source, target)
    target.chmod(0o755)
    return target
