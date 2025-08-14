from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List


@dataclass
class LayoutConfig:
    row_wrap: int = 10
    step_x: int = 300
    step_y: int = 200
    width: int = 180
    height: int = 100
    margin_x: int = 40
    margin_y: int = 40

    def calculate_position(self, index: int) -> tuple[int, int]:
        x = self.margin_x + (index % self.row_wrap) * self.step_x
        y = self.margin_y + (index // self.row_wrap) * self.step_y
        return x, y


@dataclass
class DiagramConfig:
    diagram_name: str = "ClassDiagram"
    diagram_version: str = "2.0"
    layout: LayoutConfig = LayoutConfig()


@dataclass
class GeneratorConfig:
    diagram: DiagramConfig = DiagramConfig()
    output_uml: str = "output.uml"
    output_notation: str = "output.notation"
    project_name: str = "GeneratedUML"
    enable_template_binding: bool = True
    strict_validation: bool = False
    pretty_print: bool = False
    types_profiles: Optional[List[str]] = None
    # Association policy
    allow_owned_end: bool = True
    annotate_owned_end: bool = True
    # Emission policy for unresolved referenced types
    emit_referenced_type_stubs: bool = False
    
    # 🚨 FALLBACK C++ PROCESSING OPTIONS
    # TODO: Remove when migrating to clang-uml C++ library
    cpp_processing_strategy: str = "fallback"  # "strict", "fallback", "display_name"
    cpp_max_corruption_level: int = 2          # 0=clean only, 3=accept all  
    cpp_preserve_raw_metadata: bool = True     # For bidirectional conversion
    cpp_enable_profiles: bool = True           # Enable C++ type profiles
    cpp_show_fallback_warnings: bool = True   # Show migration warnings


DEFAULT_CONFIG = GeneratorConfig()

__all__ = [
    "LayoutConfig",
    "DiagramConfig", 
    "GeneratorConfig",
    "DEFAULT_CONFIG",
]