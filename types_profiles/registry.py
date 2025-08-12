from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import json
import os


@dataclass
class ContainerProps:
    kind: str
    element_args: List[int]
    multiplicity: str
    aggregation: str
    end_name: Optional[str] = None
    end_names: Optional[List[str]] = None


@dataclass
class PtrProps:
    ownership: str
    aggregation: str


class TypeLibRegistry:
    def __init__(self, profiles: Optional[List[Dict[str, Any]]] = None) -> None:
        self.aliases: Dict[str, str] = {}
        self.rules: List[Dict[str, Any]] = []
        if profiles:
            for prof in profiles:
                self._merge_profile(prof)

    def _merge_profile(self, profile: Dict[str, Any]) -> None:
        self.aliases.update(profile.get("aliases", {}))
        self.rules.extend(profile.get("rules", []))

    def resolve_base(self, base: str) -> str:
        return self.aliases.get(base, base)

    def _match(self, base: str) -> Optional[Dict[str, Any]]:
        for rule in self.rules:
            m = rule.get("match", {})
            bases = m.get("base") or []
            if base in bases:
                return rule
        return None

    def container_of(self, base: str) -> Optional[ContainerProps]:
        base = self.resolve_base(base)
        rule = self._match(base)
        if rule and rule.get("classify") == "container":
            c = rule.get("container", {})
            return ContainerProps(
                kind=c.get("kind", "sequential"),
                element_args=c.get("element_args", [0]),
                multiplicity=c.get("multiplicity", "*"),
                aggregation=c.get("aggregation", "none"),
                end_name=c.get("end_name"),
                end_names=c.get("end_names"),
            )
        return None

    def ptr_of(self, base: str) -> Optional[PtrProps]:
        base = self.resolve_base(base)
        rule = self._match(base)
        if rule and rule.get("classify") == "pointer":
            p = rule.get("pointer", {})
            return PtrProps(
                ownership=p.get("ownership", "shared"),
                aggregation=p.get("aggregation", "shared"),
            )
        return None


def _load_single_profile(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        if path.lower().endswith(('.yml', '.yaml')):
            try:
                import yaml  # type: ignore
            except Exception as e:
                raise RuntimeError(f"YAML profile provided but PyYAML not installed: {path}") from e
            return yaml.safe_load(f) or {}
        return json.load(f)


def load_profiles(paths: List[str]) -> TypeLibRegistry:
    profiles: List[Dict[str, Any]] = []
    for p in paths:
        if not p:
            continue
        if not os.path.isfile(p):
            raise FileNotFoundError(f"Type profile file not found: {p}")
        profiles.append(_load_single_profile(p))
    return TypeLibRegistry(profiles)

