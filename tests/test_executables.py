from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aermod_screening.executables import stage_executable


class ExecutableTests(unittest.TestCase):
    def test_stage_executable_preserves_windows_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source" / "makemet.exe"
            source.parent.mkdir()
            source.write_bytes(b"engine")
            destination = root / "run"
            destination.mkdir()

            staged = stage_executable(source, destination)

            self.assertEqual(staged.name, "makemet.exe")
            self.assertEqual(staged.read_bytes(), b"engine")
