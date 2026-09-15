"""CEML - Circuit Engineering Markup Language.

Core library for parsing, representing, and validating CEML (.ci) analog circuit descriptions.
"""

from ceml.models import (
    Circuit,
    Component,
    Node,
    NodeType,
    ComponentType,
    Polarity,
    Regime,
    AcBehavior,
    ParsedValue,
    Specs,
    SpecItem,
    FunctionCall,
    ValidationError,
    ValidationWarning,
    ValidationSuggestion,
    ValidationResult,
)
from ceml.parser import load, loads, CemlParseError
from ceml.validator import validate, CemlValidationError

__all__ = [
    "load",
    "loads",
    "validate",
    "Circuit",
    "Component",
    "Node",
    "NodeType",
    "ComponentType",
    "Polarity",
    "Regime",
    "AcBehavior",
    "ParsedValue",
    "Specs",
    "SpecItem",
    "FunctionCall",
    "ValidationError",
    "ValidationWarning",
    "ValidationSuggestion",
    "ValidationResult",
    "CemlValidationError",
    "CemlParseError",
]

__version__ = "0.1.0"
