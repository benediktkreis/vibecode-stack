#!/usr/bin/env python3
"""Build config.runtime.yaml — include GitHub Copilot only when tokens exist."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

BASE_CONFIG = Path(os.environ.get("LITELLM_BASE_CONFIG", "/app/config.yaml"))
RUNTIME_CONFIG = Path(os.environ.get("LITELLM_RUNTIME_CONFIG", "/app/config.runtime.yaml"))
COPILOT_INCLUDE = "configs/github-copilot.yaml"
COPILOT_API_KEY_URL = "https://api.github.com/copilot_internal/v2/token"
MIN_TOKEN_TTL_SECONDS = 60
TOKEN_DIR = Path(
    os.environ.get(
        "GITHUB_COPILOT_TOKEN_DIR",
        "/root/.config/litellm/github_copilot",
    )
)
ACCESS_TOKEN_FILE = TOKEN_DIR / "access-token"
API_KEY_FILE = TOKEN_DIR / "api-key.json"


def api_key_json_is_valid() -> bool:
    if not API_KEY_FILE.is_file() or API_KEY_FILE.stat().st_size == 0:
        return False

    try:
        with API_KEY_FILE.open() as f:
            api_key_info = json.load(f)
    except Exception as exc:
        print(f"GitHub Copilot: ignoring unreadable api-key.json ({exc})", flush=True)
        return False

    expires_at = api_key_info.get("expires_at", 0)
    return bool(
        api_key_info.get("token")
        and expires_at > time.time() + MIN_TOKEN_TTL_SECONDS
    )


def read_access_token() -> str | None:
    if not ACCESS_TOKEN_FILE.is_file() or ACCESS_TOKEN_FILE.stat().st_size == 0:
        return None

    token = ACCESS_TOKEN_FILE.read_text().strip()
    return token or None


def refresh_api_key(access_token: str) -> bool:
    request = urllib.request.Request(
        COPILOT_API_KEY_URL,
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "editor-version": "vscode/1.85.1",
            "editor-plugin-version": "copilot/1.155.0",
            "user-agent": "GithubCopilot/1.155.0",
            "authorization": f"token {access_token}",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            api_key_info = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        print(f"GitHub Copilot: token refresh failed ({exc})", flush=True)
        return False

    expires_at = api_key_info.get("expires_at", 0)
    if (
        not api_key_info.get("token")
        or expires_at <= time.time() + MIN_TOKEN_TTL_SECONDS
    ):
        print("GitHub Copilot: token refresh response was not usable", flush=True)
        return False

    API_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with API_KEY_FILE.open("w") as f:
        json.dump(api_key_info, f)

    return True


def copilot_is_configured() -> bool:
    if api_key_json_is_valid():
        return True

    access_token = read_access_token()
    if access_token is None:
        return False

    return refresh_api_key(access_token)


def main() -> int:
    with BASE_CONFIG.open() as f:
        config = yaml.safe_load(f) or {}

    includes: list = list(config.get("include") or [])
    if copilot_is_configured():
        if COPILOT_INCLUDE not in includes:
            includes.append(COPILOT_INCLUDE)
        print(
            f"GitHub Copilot: enabled ({COPILOT_INCLUDE}) — credentials validated in {TOKEN_DIR}",
            flush=True,
        )
    else:
        includes = [i for i in includes if i != COPILOT_INCLUDE]
        print(
            f"GitHub Copilot: skipped — no usable credentials in {TOKEN_DIR} "
            "(run ./scripts/auth-github-copilot.sh, then restart)",
            flush=True,
        )

    config["include"] = includes

    with RUNTIME_CONFIG.open("w") as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)

    return 0


if __name__ == "__main__":
    sys.exit(main())
