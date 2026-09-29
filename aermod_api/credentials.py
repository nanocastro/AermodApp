from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

from dotenv import dotenv_values, set_key

from .config import Settings


SERVICE_NAME = "AERMOD Screening Mendoza"
FIELDS = ("earthdata_username", "earthdata_password", "cdsapi_key")


class CredentialStore:
    """Stores packaged-app secrets in the operating-system credential vault."""

    def __init__(self, fallback_path: Path, initial: Settings) -> None:
        self.fallback_path = fallback_path.resolve()
        self.initial = initial

    def _keyring(self):
        if os.name != "nt":
            return None
        try:
            import keyring

            keyring.get_keyring().priority
            return keyring
        except Exception:
            return None

    def values(self) -> dict[str, str]:
        fallback = dotenv_values(self.fallback_path) if self.fallback_path.is_file() else {}
        values = {
            "earthdata_username": str(fallback.get("EARTHDATA_USERNAME") or self.initial.earthdata_username),
            "earthdata_password": str(fallback.get("EARTHDATA_PASSWORD") or self.initial.earthdata_password),
            "cdsapi_key": str(fallback.get("CDSAPI_KEY") or self.initial.cdsapi_key),
        }
        keyring = self._keyring()
        if keyring:
            for field in FIELDS:
                try:
                    stored = keyring.get_password(SERVICE_NAME, field)
                except Exception:
                    stored = None
                if stored is not None:
                    values[field] = stored
        return values

    def save(self, *, earthdata_username: str = "", earthdata_password: str = "", cdsapi_key: str = "") -> str:
        values = self.values()
        if earthdata_username:
            values["earthdata_username"] = earthdata_username.strip()
        if earthdata_password:
            values["earthdata_password"] = earthdata_password
        if cdsapi_key:
            values["cdsapi_key"] = cdsapi_key.strip()
        keyring = self._keyring()
        if keyring:
            try:
                for field, value in values.items():
                    keyring.set_password(SERVICE_NAME, field, value)
                return "credential_manager"
            except Exception:
                pass
        self.fallback_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.fallback_path.exists():
            self.fallback_path.touch(mode=0o600)
        for field, value in values.items():
            set_key(str(self.fallback_path), field.upper(), value, quote_mode="always")
        try:
            os.chmod(self.fallback_path, 0o600)
        except OSError:
            pass
        return "local_file"

    def apply(self, settings: Settings) -> Settings:
        values = self.values()
        return replace(settings, **values)

    def status(self) -> dict:
        values = self.values()
        return {
            "earthdata_configured": bool(values["earthdata_username"] and values["earthdata_password"]),
            "cds_configured": bool(values["cdsapi_key"]),
            "storage": "credential_manager" if self._keyring() else "local_file",
        }
