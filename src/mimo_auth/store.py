"""Local profile storage."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Iterable, Optional
from uuid import uuid4

from .models import Profile


DEFAULT_STORE_PATH = Path.home() / ".mimo-auth" / "profiles.json"


class ProfileStore:
    def __init__(self, path: Path = DEFAULT_STORE_PATH) -> None:
        self.path = path

    def load_data(self) -> dict:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def load(self) -> Dict[str, Profile]:
        data = self.load_data()
        profiles = data.get("profiles", {})
        return {
            alias: Profile.from_dict(profile_data)
            for alias, profile_data in profiles.items()
        }

    def save(self, profiles: Dict[str, Profile], active_alias: Optional[str] = None) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "active_alias": active_alias,
            "profiles": {
                alias: profile.to_dict()
                for alias, profile in sorted(profiles.items())
            }
        }
        temp_name = f".{self.path.name}.{os.getpid()}.{uuid4().hex}.tmp"
        temp_path = self.path.with_name(temp_name)
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
        temp_path.replace(self.path)
        self.path.chmod(0o600)

    def list_profiles(self) -> Iterable[Profile]:
        return self.load().values()

    def get(self, alias: str) -> Optional[Profile]:
        return self.load().get(alias)

    def upsert(self, profile: Profile) -> None:
        profiles = self.load()
        profiles[profile.alias] = profile
        self.save(profiles, self.get_active_alias())

    def remove(self, alias: str) -> bool:
        profiles = self.load()
        existed = alias in profiles
        if existed:
            del profiles[alias]
            active_alias = self.get_active_alias()
            self.save(profiles, None if active_alias == alias else active_alias)
        return existed

    def get_active_alias(self) -> Optional[str]:
        active_alias = self.load_data().get("active_alias")
        return active_alias if isinstance(active_alias, str) else None

    def set_active_alias(self, alias: str) -> None:
        profiles = self.load()
        if alias not in profiles:
            raise KeyError(f"Profile '{alias}' not found.")
        self.save(profiles, alias)
