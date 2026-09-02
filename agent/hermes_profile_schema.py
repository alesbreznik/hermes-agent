"""
Hermes Dedicated Agent Blueprint & Profile Specification Contract.
Location: contracts/hermes_profile_schema.py
Defines the schema for dedicated Hermes OS Copilot personas, strictly decoupled
from Supergraph's internal 31 execution agent templates.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HermesProfileSpec(BaseModel):
    """Declarative specification for an autonomous Hermes Copilot profile."""
    name: str = Field(description="Unique profile name (e.g. general, terminal, delegator, browser, coder)")
    description: str = Field(description="Operational role and responsibilities")
    allowed_toolsets: List[str] = Field(
        default_factory=list,
        description="Whitelisted Hermes toolsets (e.g. ['terminal', 'supergraph', 'browser'])",
    )
    attached_sidecars: List[str] = Field(
        default_factory=list,
        description="Selective FastMCP sidecars to mount (e.g. ['sidecar_memory', 'sidecar_chrome_devtools'])",
    )
    system_prompt_overlay: str = Field(
        default="",
        description="Specialized persona prompt injected into system prompt",
    )
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    preferred_model: str = Field(
        default="hermes3:8b",
        description="Default local model target (hermes3:8b on GPU 0 or gemma4:26b on GPU 1)",
    )
    max_turns: int = Field(default=30, description="Maximum execution turns per mission")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom user configuration tags")
