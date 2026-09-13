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
    **kwargs: Any,
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

    for attempt in range(2):
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(f"{BRIDGE_URL}/v1/bridge/mission", json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    task_id = data.get("task_id", mission_id)
                    return {
                        "status": "dispatched",
                        "mission_id": mission_id,
                        "task_id": task_id,
                        "tracking_url": f"{BRIDGE_URL}/v1/bridge/task/{task_id}",
                        "message": f"Mission accepted by Supergraph Coordinator. Ticket: {task_id}",
                        "conversational_hint": (
                            f"Inform the user warmly that mission '{intent[:60]}' has been dispatched to Supergraph OS "
                            f"(Ticket: {task_id}). Explain that progress is tracked in Kanban, and that you remain available "
                            "for questions or further instructions while it executes in the background."
                        ),
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
            if attempt == 0:
                try:
                    with httpx.Client(timeout=3.0) as client:
                        client.get("http://127.0.0.1:9005/wake")
                    time.sleep(1.0)
                    continue
                except Exception:
                    pass
            return {
                "status": "offline",
                "error": str(e),
                "message": (
                    f"[NOTICE] Supergraph Bridge is currently unreachable at {BRIDGE_URL}. "
                    "Ensure Supergraph OS stack is started via Watchdog Broker (Port 9005) or Port 8003 daemon."
                ),
            }


def supergraph_status(task_id: str, **kwargs: Any) -> Dict[str, Any]:
    """
    Queries active execution status, DAG progress, and milestone events for a delegated task.
    """
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(f"{BRIDGE_URL}/v1/bridge/task/{task_id}")
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "status": data.get("status", "found"),
                    "task_id": task_id,
                    "task_data": data,
                    "message": f"Task {task_id} retrieved from Supergraph Bridge (Port 8003)",
                }
            elif resp.status_code == 404:
                return {
                    "status": "not_found",
                    "task_id": task_id,
                    "message": f"Task {task_id} not found in Hermes Kanban",
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
    **kwargs: Any,
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


STANDALONE_PORT_MAP = {
    "researcher": 5033,
    "gpt_researcher": 5033,
    "gpt_researcher_agent": 5033,
    "browser_use": 5025,
    "browser_use_agent": 5025,
    "browser": 5025,
    "open_interpreter": 5026,
    "open_interpreter_agent": 5026,
    "interpreter": 5026,
    "openhands": 5030,
    "openhands_agent": 5030,
    "letta": 5031,
    "letta_memory": 5031,
    "letta_memory_agent": 5031,
    "db_gpt": 5032,
    "db_gpt_agent": 5032,
}


def list_standalone_agents(**kwargs: Any) -> Dict[str, Any]:
    """
    Lists available standalone execution microagents (GPT-Researcher, Browser-Use,
    Open-Interpreter, OpenHands, Letta Memory, DB-GPT) and their status.
    """
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(f"{BRIDGE_URL}/v1/bridge/standalone_agents")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass

    # Diagnostic fallback listing
    agents = [
        {"engine_id": "gpt_researcher_agent", "name": "GPT-Researcher", "port": 5033, "description": "Deep multi-source web research & report synthesis."},
        {"engine_id": "browser_use_agent", "name": "Browser-Use", "port": 5025, "description": "Autonomous browser DOM automation and scraping."},
        {"engine_id": "open_interpreter_agent", "name": "Open-Interpreter", "port": 5026, "description": "Stateful multi-language REPL code executor."},
        {"engine_id": "openhands_agent", "name": "OpenHands", "port": 5030, "description": "Repository engineering and software sandboxes."},
        {"engine_id": "letta_memory_agent", "name": "Letta Memory", "port": 5031, "description": "Tiered persistent memory block management."},
        {"engine_id": "db_gpt_agent", "name": "DB-GPT", "port": 5032, "description": "Text-to-SQL synthesis and structured database queries."},
    ]
    return {"standalone_agents": agents, "total": len(agents), "status": "fallback_catalog"}


def standalone_agent_execute(
    agent_name: Optional[str] = None,
    task: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    goal: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Instantiates or calls a standalone microagent (e.g. gpt_researcher, open_interpreter, browser_use)
    with a structured task and parameters.
    """
    effective_agent = agent_name or agent_id or "gpt_researcher_agent"
    effective_task = task or goal or ""

    payload = {
        "agent_name": effective_agent,
        "task": effective_task,
        "parameters": parameters or {},
        "session_id": session_id or os.environ.get("HERMES_SESSION_ID", "hermes_standalone"),
    }

    # 1. Attempt Bridge API
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(f"{BRIDGE_URL}/v1/bridge/standalone_agents/dispatch", json=payload)
            if resp.status_code in [200, 201]:
                return resp.json()
    except Exception:
        pass

    # 2. Attempt direct socket to standalone agent
    clean_name = effective_agent.strip().lower().replace("-", "_")
    port = STANDALONE_PORT_MAP.get(clean_name)
    if port:
        try:
            with httpx.Client(timeout=10.0) as client:
                direct_payload = dict(parameters or {})
                direct_payload["task"] = effective_task
                if session_id:
                    direct_payload["session_id"] = session_id
                resp = client.post(f"http://127.0.0.1:{port}/v1/run", json=direct_payload)
                if resp.status_code in [200, 201]:
                    return resp.json()
        except Exception:
            pass

    # 3. Diagnostic Mock Fallback compliant with Rule 3
    logger.warning(
        f"[TECHNICAL ERROR: LIVE SERVICE OFFLINE -> DIAGNOSTIC FALLBACK ACTIVATED] "
        f"Standalone agent '{effective_agent}' unavailable via Bridge or Direct Port {port}."
    )
    return {
        "status": "completed_fallback",
        "agent_name": effective_agent,
        "task": effective_task,
        "output": f"[DIAGNOSTIC FALLBACK] Standalone agent '{effective_agent}' processed: {effective_task[:80]}...",
        "notice": "[TECHNICAL ERROR: LIVE SERVICE OFFLINE -> DIAGNOSTIC FALLBACK ACTIVATED]",
    }


def run_deep_research(
    topic: str,
    report_type: str = "research_report",
    sources: Optional[List[str]] = None,
    session_id: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Specialized deep research tool for the Hermes Researcher Agent.
    Analyzes complex questions and synthesizes multi-source research briefs via GPT-Researcher.
    """
    params = {
        "report_type": report_type,
        "sources": sources or [],
    }
    result = standalone_agent_execute(
        agent_name="gpt_researcher_agent",
        task=topic,
        parameters=params,
        session_id=session_id,
        **kwargs,
    )
    # Mirror research brief into Obsidian Knowledge Vault (01_Tasks/Research/)
    try:
        from pathlib import Path
        import re
        from datetime import datetime
        vault_root = Path(os.environ.get("KNOWLEDGE_VAULT_PATH", "/home/ales/knowledge_vault"))
        research_dir = vault_root / "01_Tasks" / "Research"
        research_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d %H:%M:%S")
        clean_slug = re.sub(r"[^\w\s-]", "", topic).strip().lower()
        slug = re.sub(r"[-\s]+", "_", clean_slug)[:40] or "research"
        filename = f"{now.strftime('%Y%m%d_%H%M%S')}_{slug}.md"
        filepath = research_dir / filename

        output_text = result.get("output") or result.get("report") or json.dumps(result, indent=2)
        safe_topic = topic.replace('"', '\\"')
        note_content = f"""---
fileClass: research-report
date: "{date_str}"
topic: "{safe_topic}"
report_type: "{report_type}"
status: pending_review
tags:
  - research
  - pending-review
---

# 🔬 Research Report: {topic[:80]}

- **Generated:** `{date_str}`
- **Report Type:** `{report_type}`
- **Status:** `#pending-review`

---

## Executive Summary & Findings
{output_text}

---

## 📋 Obsidian Review Checklist
- [ ] Verify sources and conclusions
- [ ] File to `02_Architecture` or `03_Memory` if permanent
- [ ] Update `status` to `reviewed`
"""
        filepath.write_text(note_content, encoding="utf-8")
        result["vault_report_path"] = str(filepath)
    except Exception as _vault_err:
        logger.debug(f"[run_deep_research] Knowledge Vault save skipped: {_vault_err}")

    return result


# --- Registry ---
try:
    from tools.registry import registry
except ImportError:
    try:
        from interfaces.hermes_bridge.supergraph_tool import registry
    except ImportError:
        registry = None

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

LIST_AGENTS_SCHEMA = {
    "name": "list_standalone_agents",
    "description": "Lists available standalone execution microagents (e.g. GPT-Researcher, Browser-Use, Open-Interpreter).",
    "parameters": {
        "type": "object",
        "properties": {},
    },
}

STANDALONE_EXEC_SCHEMA = {
    "name": "standalone_agent_execute",
    "description": "Executes a specialized task on a standalone microagent (e.g. gpt_researcher, open_interpreter, browser_use, openhands, db_gpt).",
    "parameters": {
        "type": "object",
        "properties": {
            "agent_name": {"type": "string", "description": "Target agent identifier: researcher, browser_use, open_interpreter, openhands, db_gpt, letta."},
            "task": {"type": "string", "description": "Structured task description or prompt."},
            "parameters": {"type": "object", "description": "Optional parameters specific to the agent."},
        },
        "required": ["agent_name", "task"],
    },
}

DEEP_RESEARCH_SCHEMA = {
    "name": "run_deep_research",
    "description": "Conducts deep multi-source web research and generates a structured research report with citations via standalone GPT-Researcher.",
    "parameters": {
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "Detailed research topic, questions, or brief."},
            "report_type": {"type": "string", "enum": ["research_report", "detailed_report", "outline"], "default": "research_report"},
            "sources": {"type": "array", "items": {"type": "string"}, "description": "Optional custom domains or URLs to prioritize."},
        },
        "required": ["topic"],
    },
}

def _to_json(res: Any) -> str:
    if isinstance(res, str):
        return res
    return json.dumps(res, ensure_ascii=False)


if registry is not None:
    registry.register(
        name="supergraph_delegate",
        toolset="supergraph",
        schema=DELEGATE_SCHEMA,
        handler=lambda args, **kw: _to_json(supergraph_delegate(**(args or {}))),
        emoji="🚀",
    )
    registry.register(
        name="supergraph_status",
        toolset="supergraph",
        schema=STATUS_SCHEMA,
        handler=lambda args, **kw: _to_json(supergraph_status(**(args or {}))),
        emoji="📡",
    )
    registry.register(
        name="supergraph_steer",
        toolset="supergraph",
        schema=STEER_SCHEMA,
        handler=lambda args, **kw: _to_json(supergraph_steer(**(args or {}))),
        emoji="🛑",
    )
    registry.register(
        name="list_standalone_agents",
        toolset="supergraph",
        schema=LIST_AGENTS_SCHEMA,
        handler=lambda args=None, **kw: _to_json(list_standalone_agents()),
        emoji="📋",
    )
    registry.register(
        name="standalone_agent_execute",
        toolset="supergraph",
        schema=STANDALONE_EXEC_SCHEMA,
        handler=lambda args, **kw: _to_json(standalone_agent_execute(**(args or {}))),
        emoji="🤖",
    )
    registry.register(
        name="run_deep_research",
        toolset="supergraph",
        schema=DEEP_RESEARCH_SCHEMA,
        handler=lambda args, **kw: _to_json(run_deep_research(**(args or {}))),
        emoji="🔬",
    )
