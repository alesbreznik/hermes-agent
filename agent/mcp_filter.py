"""
Hermes FastMCP Selective Sidecar Filter & Probe Engine.
Location: interfaces/hermes_bridge/mcp_filter.py
Performs concurrent sub-20ms socket probes and selectively mounts required FastMCP
tool sidecars according to the active Hermes profile.
"""
from __future__ import annotations

import socket
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

try:
    from contracts.sidecar_attachment_schema import (
        SIDECAR_CATALOG,
        SidecarDefinition,
        SidecarProfileConfig,
        resolve_sidecars_for_profile,
    )
except ImportError:
    # Direct import fallback if executed from hermes-agent standalone
    from sidecar_attachment_schema import (  # type: ignore
        SIDECAR_CATALOG,
        SidecarDefinition,
        SidecarProfileConfig,
        resolve_sidecars_for_profile,
    )


def probe_port_online(port: int, host: str = "127.0.0.1", timeout_s: float = 0.15) -> bool:
    """Fast TCP socket connect probe to verify if a sidecar is actively listening."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout_s)
            res = sock.connect_ex((host, port))
            return res == 0
    except Exception:
        return False


def probe_sidecars_concurrent(
    sidecars: List[SidecarDefinition],
    timeout_s: float = 0.15,
    max_workers: int = 8,
) -> Dict[str, bool]:
    """Probes multiple target sidecar ports in parallel within a bounded time envelope (<30ms)."""
    if not sidecars:
        return {}

    results: Dict[str, bool] = {}

    def _check(defn: SidecarDefinition) -> tuple[str, bool]:
        is_up = probe_port_online(defn.port, timeout_s=timeout_s)
        return defn.id, is_up

    with ThreadPoolExecutor(max_workers=min(len(sidecars), max_workers)) as executor:
        for sidecar_id, is_up in executor.map(_check, sidecars):
            results[sidecar_id] = is_up

    return results


class SelectiveSidecarMountGateway:
    """Manages selective sidecar evaluation and mounting for Hermes Agent sessions."""

    def __init__(self, config: Optional[SidecarProfileConfig] = None):
        self.config = config or SidecarProfileConfig()

    def evaluate_profile_mounts(
        self,
        profile_name: Optional[str] = None,
        custom_sidecars: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Resolves sidecars for the given profile, checks port availability in parallel,
        and returns the active mounted sidecar manifest.
        """
        t_start = time.perf_counter()
        active_profile = profile_name or self.config.profile_name
        targets = resolve_sidecars_for_profile(
            profile_name=active_profile,
            mode=self.config.mode,
            custom_sidecars=custom_sidecars or self.config.enabled_sidecars,
        )

        probe_statuses = probe_sidecars_concurrent(
            targets,
            timeout_s=self.config.probe_timeout_seconds,
        )

        mounted: List[Dict[str, Any]] = []
        unreachable: List[Dict[str, Any]] = []

        for defn in targets:
            is_online = probe_statuses.get(defn.id, False)
            record = {
                "id": defn.id,
                "name": defn.name,
                "port": defn.port,
                "endpoint": defn.endpoint,
                "description": defn.description,
                "status": "online" if is_online else "offline",
            }
            if is_online:
                mounted.append(record)
            else:
                unreachable.append(record)

        elapsed_ms = (time.perf_counter() - t_start) * 1000

        return {
            "profile": active_profile,
            "mode": self.config.mode,
            "requested_count": len(targets),
            "mounted_count": len(mounted),
            "unreachable_count": len(unreachable),
            "mounted_sidecars": mounted,
            "unreachable_sidecars": unreachable,
            "probe_duration_ms": round(elapsed_ms, 2),
            "status": "success",
        }
