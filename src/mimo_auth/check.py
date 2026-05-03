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
        return CheckResult(False, status, explain_http_status(status))
    except urllib.error.HTTPError as exc:
        return CheckResult(False, exc.code, explain_http_status(exc.code))
    except urllib.error.URLError as exc:
        return CheckResult(False, None, str(exc.reason))
    except TimeoutError:
        return CheckResult(False, None, "Timed out")
    except Exception as exc:
        return CheckResult(False, None, exc.__class__.__name__)


def explain_http_status(status: int) -> str:
    if status == 400:
        return "Bad request. Check the model name, endpoint URL, and request compatibility."
    if status == 401:
        return "Authentication failed. Check whether the API key/token is correct and still active."
    if status == 402:
        return "Payment or quota required. Check account balance, billing status, or Token Plan quota."
    if status == 403:
        return "Permission denied. Check whether this key is allowed to use the selected MiMo endpoint/model."
    if status == 404:
        return "Endpoint not found. Check the base_url and make sure it points to the Anthropic-compatible MiMo endpoint."
    if status == 429:
        return "Rate limited or quota exhausted. Wait and retry, or check current quota limits."
    if 500 <= status < 600:
        return "MiMo server error. Retry later; if it persists, check MiMo platform status or support."
    return "Unexpected HTTP response. Check the profile endpoint, key, model, and MiMo account status."
