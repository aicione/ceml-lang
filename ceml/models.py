"""CEML Models.

Defines the Abstract Syntax Tree (AST) and data structures for CEML circuits,
nodes, components, pinouts, and specification entries using Python native dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Union


class NodeType(str, Enum):
    GROUND = "ground"
    SUPPLY = "supply"
    INTERNAL = "internal"
    INPUT = "input"
    OUTPUT = "output"
    BIDIR = "bidir"


class ComponentType(str, Enum):
    # Passives
    RESISTOR = "resistor"
    CAPACITOR = "capacitor"
    INDUCTOR = "inductor"

    # Semiconductors
    BJT = "BJT"
    MOSFET = "MOSFET"
    JFET = "JFET"
    DIODE = "diode"

    # Sources
    VOLTAGE_SOURCE = "voltage_source"
    CURRENT_SOURCE = "current_source"
    VCVS = "VCVS"
    VCCS = "VCCS"
    CCVS = "CCVS"
    CCCS = "CCCS"

    # Complex
    OPAMP = "opamp"


class Polarity(str, Enum):
    # BJT
    NPN = "NPN"
    PNP = "PNP"
    # MOSFET
    NMOS = "NMOS"
    PMOS = "PMOS"
    # JFET
    N = "N"
    P = "P"


class Regime(str, Enum):
    DC = "DC"
    AC = "AC"


class AcBehavior(str, Enum):
    SHORT_CIRCUIT = "short_circuit"
    OPEN_CIRCUIT = "open_circuit"


@dataclass
class ParsedValue:
    """Represents a component or node value, preserving raw string and numeric magnitude."""
    raw: str
    numeric: Optional[float] = None
    is_symbolic: bool = False
    unit: Optional[str] = None

    def __repr__(self) -> str:
        if self.numeric is not None:
            return f"ParsedValue(raw='{self.raw}', numeric={self.numeric})"
        return f"ParsedValue(raw='{self.raw}', is_symbolic={self.is_symbolic})"


@dataclass
class Node:
    """Circuit node declaration."""
    id: str
    type: NodeType = NodeType.INTERNAL
    value: Optional[ParsedValue] = None
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class DependentControl:
    """Control block for dependent sources (VCVS, VCCS, CCVS, CCCS)."""
    type: str  # "voltage" or "current"
    pins: list[str] = field(default_factory=list)


@dataclass
class Component:
    """Circuit component declaration."""
    id: str
    type: str
    pins: Union[list[str], dict[str, str]]
    value: Optional[ParsedValue] = None
    role: Optional[str] = None
    model: Optional[str] = None
    ac_behavior: Optional[AcBehavior] = None
    polarized: Optional[bool] = None
    regime: Optional[Regime] = None
    polarity: Optional[Polarity] = None
    rms: Optional[bool] = None
    phase: Optional[float] = None
    gain: Optional[Union[float, str]] = None
    control: Optional[DependentControl] = None
    raw_data: dict[str, Any] = field(default_factory=dict)

    def get_connected_nodes(self) -> list[str]:
        """Returns all node IDs referenced in this component's pins and control blocks."""
        connected: list[str] = []
        if isinstance(self.pins, list):
            connected.extend(self.pins)
        elif isinstance(self.pins, dict):
            for v in self.pins.values():
                if v is not None:
                    connected.append(str(v))
        if self.control and self.control.pins:
            connected.extend(self.control.pins)
        return connected


@dataclass
class FunctionCall:
    """Represents a reserved or custom function call in given/find."""
    name: str
    args: list[str] = field(default_factory=list)
    has_hf: bool = False
    raw: str = ""

    def __repr__(self) -> str:
        args_str = ", ".join(self.args)
        if self.has_hf:
            args_str = f"{args_str}, hf" if args_str else "hf"
        return f"{self.name}({args_str})"


@dataclass
class SpecItem:
    """Single item in specs (given or find)."""
    target: Union[str, FunctionCall]
    value: Optional[ParsedValue] = None
    raw: str = ""

    @property
    def target_name(self) -> str:
        if isinstance(self.target, FunctionCall):
            return self.target.name
        return self.target


@dataclass
class Specs:
    """Circuit specifications (given and find)."""
    given: list[SpecItem] = field(default_factory=list)
    find: list[SpecItem] = field(default_factory=list)


@dataclass
class Circuit:
    """Top-level CEML circuit representation."""
    ceml_version: str
    circuit_id: str
    description: Optional[str] = None
    nodes: dict[str, Node] = field(default_factory=dict)
    components: dict[str, Component] = field(default_factory=dict)
    specs: Optional[Specs] = None
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationError:
    """Fatal validation error that prevents analysis."""
    message: str
    code: str
    component_id: Optional[str] = None
    node_id: Optional[str] = None


@dataclass
class ValidationWarning:
    """Warning indicating an assumed default or non-standard pattern."""
    message: str
    code: str
    component_id: Optional[str] = None
    node_id: Optional[str] = None


@dataclass
class ValidationSuggestion:
    """Best practice recommendation."""
    message: str
    code: str
    component_id: Optional[str] = None


@dataclass
class ValidationResult:
    """Structured report of circuit validation."""
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationWarning] = field(default_factory=list)
    suggestions: list[ValidationSuggestion] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0
