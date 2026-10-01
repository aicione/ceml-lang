"""CEML Schematic Rendering and Diagram Generation Package.

Provides 2D schematic diagram generation from CEML Circuit AST models
using SchemDraw and canonical electronic layout conventions.
"""

from ceml.schematic.layout import CircuitLayoutPlan, StageLayout, plan_circuit_layout
from ceml.schematic.renderer import create_schematic_drawing, render_circuit

__all__ = [
    "render_circuit",
    "create_schematic_drawing",
    "plan_circuit_layout",
    "CircuitLayoutPlan",
    "StageLayout",
]
