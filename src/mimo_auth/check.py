"""Profile connectivity checks for Xiaomi MiMo."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from .models import Profile


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    status: Optional[int]
    message: str


def check_profile(profile: Profile, *, model: str, timeout: float) -> CheckResult:
    url = profile.base_url.rstrip("/") + "/v1/messages"
    payload = {
        "model": model,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "1"}],
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        method="POST",
        data=data,
        headers={
            "api-key": profile.api_key,
            "x-api-key": profile.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.getcode()
        if 200 <= status < 300:
            return CheckResult(True, status, "OK")
        return CheckResult(False, status, f"HTTP {status}")
    except urllib.error.HTTPError as exc:
        return CheckResult(False, exc.code, f"HTTP {exc.code}")
    except urllib.error.URLError as exc:
        return CheckResult(False, None, str(exc.reason))
    except TimeoutError:
        return CheckResult(False, None, "Timed out")
    except Exception as exc:
        return CheckResult(False, None, exc.__class__.__name__)

