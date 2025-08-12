from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List


@dataclass
class GeneratorOptions:
    output_uml: str = "output.uml"
    output_notation: str = "output.notation"
    project_name: str = "GeneratedUML"
    enable_template_binding: bool = True
    strict_validation: bool = False
    pretty_print: bool = False
    types_profiles: Optional[List[str]] = None


DEFAULT_GENERATOR_OPTIONS = GeneratorOptions()


