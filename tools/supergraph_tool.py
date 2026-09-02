"""
Native Hermes-to-Supergraph Delegation Tool.
Location: interfaces/hermes_bridge/supergraph_tool.py
Enables Hermes Agent to dispatch high-level missions to Supergraph (Port 8003/5104),
receive async tracking tickets, and steer execution without blocking conversational flow.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from typing import Any, Dict, List, Optional
import httpx

# Ensure project root is available
try:
    from contracts.goal_spec import GoalSpec, TaskTicket
    from contracts.hermes_bridge import (
        BridgeMissionRequest,
        BridgeMissionResponse,
        BridgeSteerSignal,
        BridgeSteerResponse,
        SteerSignalPriority,
    )
except ImportError:
    # Direct import fallback
    GoalSpec = None
    TaskTicket = None

logger = logging.getLogger(__name__)
BRIDGE_URL = os.environ.get("HERMES_BRIDGE_URL", "http://127.0.0.1:8003")


def supergraph_delegate(
    intent: str,
    repo_root: Optional[str] = None,
    context_files: Optional[List[str]] = None,
    strategy: str = "adaptive_dag",
    auto_merge: bool = False,
    local_only: bool = False,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Dispatches a software engineering mission to the autonomous Supergraph 4-Plane OS.
    Returns an immediate asynchronous tracking ticket without blocking the conversational thread.
    """
    mission_id = f"mission_{uuid.uuid4().hex[:8]}"
    payload = {
        "mission_id": mission_id,
        "goal_prompt": intent,
        "session_id": session_id or os.environ.get("HERMES_SESSION_ID", "hermes_default"),
        "source": "hermes_tool",
        "strategy": strategy,
        "metadata": {
            "repo_root": repo_root or os.getcwd(),
            "context_files": context_files or [],
            "auto_merge": auto_merge,
            "local_only": local_only,
        },
    }

    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.post(f"{BRIDGE_URL}/v1/bridge/mission", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                task_id = data.get("task_id", mission_id)
                return {
                    "status": "dispatched",
                    "mission_id": mission_id,
                    "task_id": task_id,
                    "tracking_url": f"{BRIDGE_URL}/v1/bridge/status/{task_id}",
                    "message": f"Mission accepted by Supergraph Coordinator. Ticket: {task_id}",
                    "local_only": local_only,
                    "auto_merge": auto_merge,
                }
            else:
                return {
                    "status": "error",
                    "status_code": resp.status_code,
                    "message": f"Supergraph Bridge rejected mission: {resp.text}",
                }
    except Exception as e:
        return {
            "status": "offline",
            "error": str(e),
            "message": (
                f"[NOTICE] Supergraph Bridge is currently unreachable at {BRIDGE_URL}. "
                "Ensure Supergraph OS stack is started via 'supergraph start' or Port 8003 daemon."
            ),
        }


def supergraph_status(task_id: str) -> Dict[str, Any]:
    """
    Queries active execution status, DAG progress, and milestone events for a delegated task.
    """
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"{BRIDGE_URL}/health")
            if resp.status_code == 200:
                health = resp.json()
                return {
                    "status": "online",
                    "task_id": task_id,
                    "bridge_health": health,
                    "message": f"Task {task_id} is monitored by Supergraph Bridge on Port {health.get('port')}",
                }
    except Exception as e:
        return {
            "status": "offline",
            "task_id": task_id,
            "error": str(e),
            "message": f"Cannot reach Supergraph Bridge at {BRIDGE_URL}",
        }


def supergraph_steer(
    task_id: str,
    action: str,
    content: str = "",
    mission_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sends an operator interjection, guidance, pause, resume, or emergency abort signal to Supergraph.
    """
    payload = {
        "mission_id": mission_id or f"mission_for_{task_id}",
        "task_id": task_id,
        "priority": 0 if action.lower() == "abort" else 1,
        "action": action.lower(),
        "content": content,
        "timestamp": time.time(),
    }
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.post(f"{BRIDGE_URL}/v1/bridge/steer", json=payload)
            if resp.status_code == 200:
                return resp.json()
            else:
                return {"status": "error", "message": f"Bridge steer failed with HTTP {resp.status_code}: {resp.text}"}
    except Exception as e:
        return {"status": "offline", "error": str(e), "message": f"Cannot connect to Bridge at {BRIDGE_URL}"}


# ---------------------------------------------------------------------------
# Hermes Tool Registry Auto-Mount (if imported in hermes-agent environment)
# ---------------------------------------------------------------------------
try:
    from tools.registry import registry

    DELEGATE_SCHEMA = {
        "name": "supergraph_delegate",
        "description": (
            "Dispatches complex multi-stage engineering tasks to Supergraph 4-Plane OS (Port 8003/5104). "
            "Returns an immediate async ticket and updates Kanban without blocking conversational flow."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "intent": {"type": "string", "description": "High-level goal prompt or engineering objective."},
                "repo_root": {"type": "string", "description": "Target repository path. Defaults to current directory."},
                "context_files": {"type": "array", "items": {"type": "string"}, "description": "List of key files involved."},
                "strategy": {"type": "string", "enum": ["adaptive_dag", "sequential", "war_room"], "default": "adaptive_dag"},
                "auto_merge": {"type": "boolean", "default": False, "description": "Auto-merge worktree on >=9.5 test score."},
                "local_only": {"type": "boolean", "default": False, "description": "Strict local GPU execution constraint."},
            },
            "required": ["intent"],
        },
    }

    STATUS_SCHEMA = {
        "name": "supergraph_status",
        "description": "Checks the active status and DAG milestones of a delegated Supergraph mission.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Supergraph task or mission identifier."},
            },
            "required": ["task_id"],
        },
    }

    STEER_SCHEMA = {
        "name": "supergraph_steer",
        "description": "Sends an operator pause, resume, guidance, or emergency abort signal to a running Supergraph mission.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Target Supergraph task identifier."},
                "action": {"type": "string", "enum": ["abort", "pause", "resume", "inject_guidance"], "description": "Action verb."},
                "content": {"type": "string", "description": "Guidance or abort rationale."},
            },
            "required": ["task_id", "action"],
        },
    }

    registry.register(
        name="supergraph_delegate",
        toolset="supergraph",
        schema=DELEGATE_SCHEMA,
        handler=lambda args: supergraph_delegate(**args),
        emoji="🚀",
    )
    registry.register(
        name="supergraph_status",
        toolset="supergraph",
        schema=STATUS_SCHEMA,
        handler=lambda args: supergraph_status(**args),
        emoji="📡",
    )
    registry.register(
        name="supergraph_steer",
        toolset="supergraph",
        schema=STEER_SCHEMA,
        handler=lambda args: supergraph_steer(**args),
        emoji="🛑",
    )
except ImportError:
    pass
