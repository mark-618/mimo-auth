"""Claude Code settings.json integration."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from .models import Profile, utc_now_iso


DEFAULT_CLAUDE_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"


class SettingsError(RuntimeError):
    pass


def load_settings(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise SettingsError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SettingsError(f"{path} must contain a JSON object")
    return data


def backup_settings(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    backup_dir = path.parent / "mimo-auth-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = utc_now_iso().replace(":", "-")
    backup_path = backup_dir / f"settings.{timestamp}.json"
    shutil.copy2(path, backup_path)
    return backup_path


def write_settings(path: Path, settings: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp"
    temp_path = path.with_name(temp_name)
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(settings, file, ensure_ascii=False, indent=2)
        file.write("\n")
    temp_path.replace(path)


def apply_profile(path: Path, profile: Profile) -> Optional[Path]:
    settings = load_settings(path)
    backup_path = backup_settings(path)
    env = settings.get("env")
    if env is None:
        env = {}
        settings["env"] = env
    if not isinstance(env, dict):
        raise SettingsError(f"{path} field 'env' must be a JSON object")
    env["ANTHROPIC_BASE_URL"] = profile.base_url
    env["ANTHROPIC_AUTH_TOKEN"] = profile.api_key
    write_settings(path, settings)
    return backup_path


def read_current_env(path: Path) -> Dict[str, Optional[str]]:
    settings = load_settings(path)
    env = settings.get("env", {})
    if not isinstance(env, dict):
        raise SettingsError(f"{path} field 'env' must be a JSON object")
    return {
        "ANTHROPIC_BASE_URL": env.get("ANTHROPIC_BASE_URL"),
        "ANTHROPIC_AUTH_TOKEN": env.get("ANTHROPIC_AUTH_TOKEN"),
    }
