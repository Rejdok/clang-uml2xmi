from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LayoutOptions:
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
class DiagramOptions:
    diagram_name: str = "ClassDiagram"
    diagram_version: str = "2.0"
    layout: LayoutOptions = LayoutOptions()


DEFAULT_DIAGRAM_OPTIONS = DiagramOptions()


