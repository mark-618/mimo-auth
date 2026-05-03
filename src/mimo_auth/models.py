"""Data models for MiMo auth profiles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict


PROFILE_TYPES = {"api", "token-plan"}
API_BASE_URL = "https://api.xiaomimimo.com/anthropic"
TOKEN_PLAN_BASE_URL = "https://token-plan-cn.xiaomimimo.com/anthropic"
DEFAULT_MODEL = "mimo-v2.5-pro"
MIMO_MODELS = [
    ("mimo-v2.5-pro", "Pro Series, 1M context"),
    ("mimo-v2-pro", "Pro Series, 1M context"),
    ("mimo-v2.5", "Omni Series, 1M context"),
    ("mimo-v2-omni", "Omni Series, 256K context"),
    ("mimo-v2-flash", "Flash Series, 256K context"),
    ("mimo-v2.5-tts", "TTS Series"),
    ("mimo-v2.5-tts-voiceclone", "TTS voice clone"),
    ("mimo-v2.5-tts-voicedesign", "TTS voice design"),
    ("mimo-v2-tts", "TTS Series"),
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class Profile:
    alias: str
    name: str
    type: str
    base_url: str
    api_key: str
    default_model: str
    created_at: str
    updated_at: str

    @classmethod
    def create(
        cls,
        *,
        alias: str,
        name: str,
        profile_type: str,
        base_url: str,
        api_key: str,
        default_model: str,
    ) -> "Profile":
        now = utc_now_iso()
        return cls(
            alias=alias,
            name=name,
            type=profile_type,
            base_url=base_url,
            api_key=api_key,
            default_model=default_model,
            created_at=now,
            updated_at=now,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Profile":
        return cls(
            alias=str(data["alias"]),
            name=str(data["name"]),
            type=str(data["type"]),
            base_url=str(data["base_url"]),
            api_key=str(data["api_key"]),
            default_model=str(data["default_model"]),
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
        )

    def to_dict(self) -> Dict[str, str]:
        return {
            "alias": self.alias,
            "name": self.name,
            "type": self.type,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "default_model": self.default_model,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def with_updates(
        self,
        *,
        name: str,
        profile_type: str,
        base_url: str,
        api_key: str,
        default_model: str,
    ) -> "Profile":
        return Profile(
            alias=self.alias,
            name=name,
            type=profile_type,
            base_url=base_url,
            api_key=api_key,
            default_model=default_model,
            created_at=self.created_at,
            updated_at=utc_now_iso(),
        )


def validate_profile_type(profile_type: str) -> None:
    if profile_type not in PROFILE_TYPES:
        allowed = ", ".join(sorted(PROFILE_TYPES))
        raise ValueError(f"type must be one of: {allowed}")


def mask_api_key(api_key: str) -> str:
    if len(api_key) <= 4:
        return "****"
    prefix = api_key[:3] if len(api_key) > 7 else ""
    return f"{prefix}****{api_key[-4:]}"
