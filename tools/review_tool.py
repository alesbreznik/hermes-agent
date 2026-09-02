"""
Hermes Operator Review Queue Tool.
Location: interfaces/hermes_bridge/review_tool.py
Enables the Hermes Copilot to inspect pending operator review items and resolve them on behalf of the user.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)
BRIDGE_URL = os.environ.get("HERMES_BRIDGE_URL", "http://127.0.0.1:8003")


def review_list_pending(urgency: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches all pending tasks awaiting human review or clarification."""
    try:
        url = f"{BRIDGE_URL}/v1/bridge/human_queue/pending"
        if urgency:
            url += f"?urgency={urgency}"
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                return resp.json()
            return [{"error": f"HTTP {resp.status_code}: {resp.text}"}]
    except Exception as e:
        return [{"status": "offline", "error": str(e), "message": f"Bridge unreachable at {BRIDGE_URL}"}]


def review_resolve(
    item_id: str,
    action: str = "approve",
    freeform_guidance: str = "",
    selected_option_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Submits operator resolution for a pending review item and unfreezes the task."""
    payload = {
        "item_id": item_id,
        "action": action,
        "freeform_guidance": freeform_guidance,
        "selected_option_id": selected_option_id,
        "resolved_by": "hermes_operator",
        "timestamp": time.time(),
    }
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.post(f"{BRIDGE_URL}/v1/bridge/human_queue/resolve", json=payload)
            if resp.status_code == 200:
                return resp.json()
            return {"status": "error", "message": f"HTTP {resp.status_code}: {resp.text}"}
    except Exception as e:
        return {"status": "offline", "error": str(e), "message": f"Bridge unreachable at {BRIDGE_URL}"}


# Hermes Tool Registry registration
try:
    from tools.registry import registry

    REVIEW_LIST_SCHEMA = {
        "name": "review_list_pending",
        "description": "Lists all pending tasks awaiting human review, clarification, or approval.",
        "parameters": {
            "type": "object",
            "properties": {
                "urgency": {"type": "string", "enum": ["low", "normal", "blocking"], "description": "Filter by urgency level."},
            },
        },
    }

    REVIEW_RESOLVE_SCHEMA = {
        "name": "review_resolve",
        "description": "Submits operator resolution for a pending review item, unfreezing the paused execution step.",
        "parameters": {
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "Target review item identifier."},
                "action": {"type": "string", "enum": ["approve", "reject", "redirect", "dismiss"], "default": "approve"},
                "freeform_guidance": {"type": "string", "description": "Clarifications or guidance for the agent."},
                "selected_option_id": {"type": "integer", "description": "Selected option identifier."},
            },
            "required": ["item_id"],
        },
    }

    registry.register(
        name="review_list_pending",
        toolset="supergraph",
        schema=REVIEW_LIST_SCHEMA,
        handler=lambda args: review_list_pending(**args),
        emoji="📝",
    )
    registry.register(
        name="review_resolve",
        toolset="supergraph",
        schema=REVIEW_RESOLVE_SCHEMA,
        handler=lambda args: review_resolve(**args),
        emoji="✅",
    )
except ImportError:
    pass
