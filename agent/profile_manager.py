"""
Hermes Dedicated Profile Manager.
Location: interfaces/hermes_bridge/profile_manager.py
Loads, validates, and manages Hermes dedicated agent blueprints and persona overlays,
enforcing strict isolation from Supergraph's 31 internal multi-agent templates.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional
import yaml

try:
    from contracts.hermes_profile_schema import HermesProfileSpec
except ImportError:
    from hermes_profile_schema import HermesProfileSpec  # type: ignore

USER_HERMES_DIR = Path.home() / ".hermes" / "profiles"
BUILTIN_HERMES_PROFILES_DIR = Path("/home/ales/hermes-agent/profiles")


class HermesProfileManager:
    """Manages discovery, loading, and isolation of Hermes dedicated agent blueprints."""

    def __init__(
        self,
        custom_profiles_dir: Optional[Path] = None,
        builtin_profiles_dir: Optional[Path] = None,
    ):
        self.custom_dir = custom_profiles_dir or USER_HERMES_DIR
        self.builtin_dir = builtin_profiles_dir or BUILTIN_HERMES_PROFILES_DIR
        self._cache: Dict[str, HermesProfileSpec] = {}

    def load_profile(self, name: str) -> HermesProfileSpec:
        """
        Loads a Hermes profile by name.
        Priority:
        1. ~/.hermes/profiles/{name}.yaml
        2. ~/.hermes/profiles/{name}/profile.yaml
        3. hermes-agent/profiles/{name}.yaml
        4. Fallback default general profile
        """
        clean_name = name.strip().lower()
        if clean_name in self._cache:
            return self._cache[clean_name]

        candidate_paths = [
            self.custom_dir / f"{clean_name}.yaml",
            self.custom_dir / f"{clean_name}.yml",
            self.custom_dir / clean_name / "profile.yaml",
            self.builtin_dir / f"{clean_name}.yaml",
            self.builtin_dir / f"{clean_name}.yml",
        ]

        for p in candidate_paths:
            if p.is_file():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                    spec = HermesProfileSpec(**data)
                    self._cache[clean_name] = spec
                    return spec
                except Exception as e:
                    # Continue to next candidate on YAML parse error
                    pass

        # Fallback to general specification
        fallback = HermesProfileSpec(
            name=clean_name,
            description=f"Auto-generated profile for {clean_name}",
            allowed_toolsets=["terminal", "file_tools", "supergraph"],
            system_prompt_overlay=f"You are operating under the '{clean_name}' persona.",
            temperature=0.7,
            preferred_model="hermes3:8b",
        )
        self._cache[clean_name] = fallback
        return fallback

    def list_profiles(self) -> List[HermesProfileSpec]:
        """Scans directories and returns all discovered Hermes profile blueprints."""
        names = set()
        specs = []

        # Built-in profiles
        if self.builtin_dir.is_dir():
            for f in self.builtin_dir.glob("*.yaml"):
                names.add(f.stem)

        # Custom user profiles
        if self.custom_dir.is_dir():
            for f in self.custom_dir.glob("*.yaml"):
                names.add(f.stem)
            for d in self.custom_dir.iterdir():
                if d.is_dir() and (d / "profile.yaml").is_file():
                    names.add(d.name)

        for name in sorted(names):
            specs.append(self.load_profile(name))

        return specs

    def get_system_prompt(self, profile_name: str, base_prompt: str = "") -> str:
        """Constructs effective system prompt with the profile's overlay."""
        profile = self.load_profile(profile_name)
        if not profile.system_prompt_overlay:
            return base_prompt

        return f"{base_prompt.strip()}\n\n[HERMES PROFILE: {profile.name.upper()}]\n{profile.system_prompt_overlay.strip()}".strip()

    def assert_supergraph_isolation(self, supergraph_templates_dir: Optional[Path] = None) -> bool:
        """
        Enforces ADR-011: Asserts zero leakage of Supergraph's internal 31 multi-agent
        templates into the Hermes profile namespace.
        """
        sg_dir = supergraph_templates_dir or Path("/home/ales/AI/agents/templates")
        if not sg_dir.is_dir():
            return True

        sg_template_names = {f.stem.lower() for f in sg_dir.glob("*.yaml")}
        hermes_profile_names = {p.name.lower() for p in self.list_profiles()}

        # Disjoint sets: Hermes profiles must not overlap with internal compiler/orchestrator templates
        overlap = sg_template_names.intersection(hermes_profile_names)
        if overlap:
            raise AssertionError(
                f"[ADR-011 VIOLATION] Hermes profiles namespace collides with internal Supergraph templates: {overlap}"
            )
        return True
