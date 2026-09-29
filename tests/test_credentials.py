from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aermod_api.config import Settings
from aermod_api.credentials import CredentialStore


class CredentialStoreTests(unittest.TestCase):
    def test_fallback_file_is_private_and_values_can_be_updated_independently(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / ".credentials"
            settings = Settings(
                database_path=Path(temporary) / "db.sqlite3",
                runs_directory=Path(temporary) / "runs",
                aermod_executable=Path("aermod"),
                makemet_executable=Path("makemet"),
                credentials_file=path,
            )
            store = CredentialStore(path, settings)
            store.save(
                earthdata_username="usuario",
                earthdata_password="contraseña",
                cdsapi_key="token-1",
            )
            store.save(cdsapi_key="token-2")

            values = store.values()
            self.assertEqual(values["earthdata_username"], "usuario")
            self.assertEqual(values["earthdata_password"], "contraseña")
            self.assertEqual(values["cdsapi_key"], "token-2")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
