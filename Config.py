#!/usr/bin/env python3
"""
Configuration classes for UML2Papyrus project.
Contains only behavioral configuration, not model structures.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum

# Import enums from UmlModel to avoid duplication
from UmlModel import Visibility, AggregationType
from uml_types import Direction


@dataclass
class LayoutConfig:
    """Configuration for element layout and positioning."""
    # Grid layout settings
    row_wrap: int = 10
    step_x: int = 300
    step_y: int = 200
    
    # Element dimensions
    width: int = 180
    height: int = 100
    
    # Margins
    margin_x: int = 40
    margin_y: int = 40
    
    def calculate_position(self, index: int) -> tuple[int, int]:
        """Calculate x, y position for element at given index."""
        x = self.margin_x + (index % self.row_wrap) * self.step_x
        y = self.margin_y + (index // self.row_wrap) * self.step_y
        return x, y


@dataclass
class DiagramConfig:
    """Configuration for diagram generation."""
    # Diagram metadata
    diagram_name: str = "ClassDiagram"
    diagram_version: str = "2.0"
    
    # Layout configuration
    layout: LayoutConfig = None
    
    def __post_init__(self):
        """Initialize default configurations if not provided."""
        if self.layout is None:
            self.layout = LayoutConfig()


@dataclass
class GeneratorConfig:
    """Main configuration for the UML generator."""
    # Diagram configuration
    diagram: DiagramConfig = None
    
    # File paths
    output_uml: str = "output.uml"
    output_notation: str = "output.notation"
    
    # Project settings
    project_name: str = "GeneratedUML"

    # Behavior flags
    enable_template_binding: bool = True   # If true, materialize instantiations with templateBinding
    strict_validation: bool = False        # If true, fail generation on validation issues
    
    # Placeholder for future type system profiles (disabled)
    
    def __post_init__(self):
        """Initialize default configurations if not provided."""
        if self.diagram is None:
            self.diagram = DiagramConfig()


# Default configuration instance
DEFAULT_CONFIG = GeneratorConfig()
