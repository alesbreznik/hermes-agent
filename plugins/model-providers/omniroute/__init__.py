"""OmniRoute AI Gateway & Unified Proxy Router provider plugin for Hermes Agent.

Provides integration with OmniRoute running on localhost:20128 (or OMNIROUTE_BASE_URL).
Supports live dynamic catalog discovery (480+ models across 14 upstream providers),
smart combo routers (auto/best-fast, auto/best-coding, auto/best-reasoning),
and zero-latency local proxy dispatch.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from typing import Any, Optional

from hermes_cli import __version__ as _HERMES_VERSION
from providers import register_provider
from providers.base import ProviderProfile

logger = logging.getLogger(__name__)

OMNIROUTE_DEFAULT_BASE_URL = "http://127.0.0.1:20128/v1"
OMNIROUTE_DEFAULT_API_KEY = "sk-omniroute-local"


def _base_url() -> str:
    return os.getenv("OMNIROUTE_BASE_URL", "").strip().rstrip("/") or OMNIROUTE_DEFAULT_BASE_URL


def _resolve_api_key() -> str:
    try:
        from hermes_cli.config import get_env_value_prefer_dotenv
        val = get_env_value_prefer_dotenv("OMNIROUTE_API_KEY")
        if val:
            return val
    except Exception:
        pass
    return os.getenv("OMNIROUTE_API_KEY", "").strip() or OMNIROUTE_DEFAULT_API_KEY


class OmniRouteProfile(ProviderProfile):
    """OmniRoute — OpenAI-compatible gateway with dynamic routing and combos."""

    def fetch_models(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 6.0,
    ) -> Optional[list[str]]:
        url = (base_url or _base_url()).rstrip("/") + "/models"
        key = api_key or _resolve_api_key()
        req = urllib.request.Request(url)
        if key:
            req.add_header("Authorization", f"Bearer {key}")
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", f"Hermes-Agent/{_HERMES_VERSION}")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
                items = data.get("data", []) if isinstance(data, dict) else data
                if isinstance(items, list):
                    ids = [
                        str(item["id"])
                        for item in items
                        if isinstance(item, dict) and item.get("id")
                    ]
                    if ids:
                        return ids
        except Exception as exc:
            logger.debug("omniroute: catalog fetch failed: %s", exc)

        return list(self.fallback_models)

    def get_max_tokens(self, model: str | None) -> int | None:
        """Safe completion token cap."""
        return 4096


omniroute = OmniRouteProfile(
    name="omniroute",
    aliases=("omnirouter", "omni"),
    display_name="OmniRoute AI Gateway",
    description="OmniRoute AI Gateway (port 20128) — unified router across 350+ providers & local combos",
    base_url=_base_url(),
    models_url=f"{_base_url()}/models",
    env_vars=("OMNIROUTE_API_KEY", "OMNIROUTE_BASE_URL"),
    auth_type="api_key",
    supports_vision=True,
    default_aux_model="auto/best-fast",
    fallback_models=(
        "auto/best-fast",
        "auto/best-coding",
        "auto/best-reasoning",
        "auto/best-vision",
        "oc/deepseek-v4-flash-free",
        "ddgw/gpt-5.4-mini",
        "cxa/gpt-5.6-sol",
    ),
)

register_provider(omniroute)
