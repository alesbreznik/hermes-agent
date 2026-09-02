"""
FastMCP Selective Sidecar Attachment Contracts.
Location: contracts/sidecar_attachment_schema.py
Defines the selective mounting policy, port registry, and profile mappings
to prevent process bloat and token overhead in Hermes Agent.
"""
from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class SidecarDefinition(BaseModel):
    """Metadata specification for a Supergraph FastMCP tool sidecar."""
    id: str = Field(description="Unique sidecar identifier (e.g. sidecar_memory)")
    name: str = Field(description="Human-readable title")
    port: int = Field(ge=5010, le=5025, description="Network port allocated to this sidecar")
    endpoint: str = Field(description="HTTP or SSE endpoint URL")
    hermes_policy: str = Field(description="'OMIT' (native Hermes used) or 'SELECTIVE' (profile mounted)")
    description: str = Field(description="Summary of tool capabilities exposed")


# Master Sidecar Registry (Ports 5010-5021)
SIDECAR_CATALOG: Dict[str, SidecarDefinition] = {
    "sidecar_workspace": SidecarDefinition(
        id="sidecar_workspace",
        name="Sandboxed Workspace I/O",
        port=5010,
        endpoint="http://127.0.0.1:5010/v1/tools",
        hermes_policy="OMIT",
        description="Path-sandboxed file search and I/O (Hermes uses native tools/file_tools.py)",
    ),
    "sidecar_execution": SidecarDefinition(
        id="sidecar_execution",
        name="Process & Sandbox Execution",
        port=5011,
        endpoint="http://127.0.0.1:5011/v1/tools",
        hermes_policy="OMIT",
        description="Bash execution and isolated sandboxing (Hermes uses native tools/terminal_tool.py)",
    ),
    "sidecar_web_research": SidecarDefinition(
        id="sidecar_web_research",
        name="Web Search & Jina Extract",
        port=5012,
        endpoint="http://127.0.0.1:5012/v1/tools",
        hermes_policy="OMIT",
        description="SearXNG and markdown scraper (Hermes uses native tools/web_tools.py)",
    ),
    "sidecar_system_os": SidecarDefinition(
        id="sidecar_system_os",
        name="OS & Process Management",
        port=5013,
        endpoint="http://127.0.0.1:5013/v1/tools",
        hermes_policy="OMIT",
        description="Host system commands and process control (Hermes native shell preferred)",
    ),
    "sidecar_memory": SidecarDefinition(
        id="sidecar_memory",
        name="Hybrid RRF Long-Term Memory",
        port=5014,
        endpoint="http://127.0.0.1:5014/v1/tools",
        hermes_policy="SELECTIVE",
        description="FTS5 + dense Qwen3 1024-d RRF semantic search across sessions",
    ),
    "sidecar_database": SidecarDefinition(
        id="sidecar_database",
        name="Postgres & PGVector Client",
        port=5015,
        endpoint="http://127.0.0.1:5015/v1/tools",
        hermes_policy="SELECTIVE",
        description="SQL schema inspection and vector query tools for database admin tasks",
    ),
    "sidecar_introspection": SidecarDefinition(
        id="sidecar_introspection",
        name="AST & Code Introspection",
        port=5016,
        endpoint="http://127.0.0.1:5016/v1/tools",
        hermes_policy="SELECTIVE",
        description="Python AST symbol extraction, dependency graph generation, and call graphs",
    ),
    "sidecar_sequential_thinking": SidecarDefinition(
        id="sidecar_sequential_thinking",
        name="Sequential Thinking Decomposer",
        port=5017,
        endpoint="http://127.0.0.1:5017/v1/tools",
        hermes_policy="OMIT",
        description="Step-by-step problem decomposition (Hermes internal thinking mode used)",
    ),
    "sidecar_ultrathink": SidecarDefinition(
        id="sidecar_ultrathink",
        name="Deep Multi-Step Reasoner",
        port=5018,
        endpoint="http://127.0.0.1:5018/v1/tools",
        hermes_policy="OMIT",
        description="Extended multi-turn planning (Hermes internal thinking mode used)",
    ),
    "sidecar_notebooklm": SidecarDefinition(
        id="sidecar_notebooklm",
        name="Document & Source Synthesizer",
        port=5019,
        endpoint="http://127.0.0.1:5019/v1/tools",
        hermes_policy="SELECTIVE",
        description="PDF parsing and multi-source document synthesis",
    ),
    "sidecar_chrome_devtools": SidecarDefinition(
        id="sidecar_chrome_devtools",
        name="Headless Browser & DOM Inspector",
        port=5020,
        endpoint="http://127.0.0.1:5020/v1/tools",
        hermes_policy="SELECTIVE",
        description="Full Chrome DevTools Protocol automation and DOM snapshots",
    ),
    "sidecar_tester": SidecarDefinition(
        id="sidecar_tester",
        name="Pytest Runner & Dynamic Gauntlet",
        port=5021,
        endpoint="http://127.0.0.1:5021/v1/tools",
        hermes_policy="OMIT",
        description="Heavy 9-tier test suites (Supergraph Supervisor handles testing)",
    ),
}

# Recommended Default Attachments by Hermes Profile
PROFILE_SIDECAR_MAP: Dict[str, List[str]] = {
    "default": [],
    "coder": ["sidecar_introspection"],
    "researcher": ["sidecar_memory", "sidecar_notebooklm"],
    "dba": ["sidecar_database", "sidecar_memory"],
    "browser": ["sidecar_chrome_devtools"],
    "architect": ["sidecar_introspection", "sidecar_memory"],
    "all": [sid for sid, defn in SIDECAR_CATALOG.items() if defn.hermes_policy == "SELECTIVE"],
}


class SidecarProfileConfig(BaseModel):
    """Configuration for selective sidecar attachment for an active Hermes session."""
    profile_name: str = Field(default="default", description="Active Hermes profile identifier")
    mode: str = Field(default="selective", description="'selective', 'all', or 'none'")
    enabled_sidecars: List[str] = Field(default_factory=list, description="Explicit whitelist of sidecar IDs")
    probe_timeout_seconds: float = Field(default=0.2, description="Fast socket probe timeout ceiling")
    fail_silently: bool = Field(default=True, description="Continue without sidecar if target port offline")


def resolve_sidecars_for_profile(
    profile_name: str = "default",
    mode: str = "selective",
    custom_sidecars: Optional[List[str]] = None,
) -> List[SidecarDefinition]:
    """
    Resolves target list of SidecarDefinition records based on profile and mounting mode.
    Guarantees that OMIT sidecars are excluded unless explicitly requested.
    """
    if mode == "none":
        return []

    if custom_sidecars:
        return [SIDECAR_CATALOG[sid] for sid in custom_sidecars if sid in SIDECAR_CATALOG]

    if mode == "all":
        return [defn for defn in SIDECAR_CATALOG.values() if defn.hermes_policy == "SELECTIVE"]

    # selective mode: lookup in profile map
    target_ids = PROFILE_SIDECAR_MAP.get(profile_name.lower(), [])
    return [SIDECAR_CATALOG[sid] for sid in target_ids if sid in SIDECAR_CATALOG]
