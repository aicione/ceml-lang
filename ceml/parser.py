"""CEML Parser.

Parses .ci files into strongly typed Circuit AST representations.
Handles engineering notation, resistor-style shorthands (e.g. 4k7),
and specs function call expressions.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional, Union

import yaml

from ceml.models import (
    AcBehavior,
    Circuit,
    Component,
    DependentControl,
    FunctionCall,
    Node,
    NodeType,
    ParsedValue,
    Polarity,
    Regime,
    SpecItem,
    Specs,
)


class CemlParseError(Exception):
    """Raised when parsing a CEML file fails due to syntax or formatting errors."""
    pass


# Multipliers for standard engineering magnitude suffixes
MAGNITUDE_SUFFIXES: dict[str, float] = {
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "m": 1e-3,
    "k": 1e3,
    "K": 1e3,  # Tolerant uppercase K for kilo (Decision #31)
    "M": 1e6,
    "G": 1e9,
}

# Regex for shorthand notation: e.g. 4k7, 3K3, 1k5, 3k9, 0m5
RE_SHORTHAND = re.compile(r"^([+-]?[0-9]+)([pnumkKMG])([0-9]+)$")

# Regex for standard suffix notation: e.g. 10k, 10K, 2m, 12p, -5k, 4.7k
RE_STANDARD_SUFFIX = re.compile(r"^([+-]?[0-9]+(?:\.[0-9]+)?)([pnumkKMG])$")

# Regex for pure numbers: e.g. 12, -5, 0.7
RE_BARE_NUMBER = re.compile(r"^([+-]?[0-9]+(?:\.[0-9]+)?)$")

# Regex for function calls: e.g. Av(Vout, Vin), Commercial(RE, min), Expr(Vo, Vin1, Vin2)
RE_FUNCTION_CALL = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)$")


def parse_engineering_value(raw: Any) -> Optional[ParsedValue]:
    """Parses a raw component or spec value into a ParsedValue.

    Supports:
    - Pure numbers: 12, 0.7, -5
    - Standard engineering suffixes: 10k, 2m, 12p, 4.7k
    - Resistor color code shorthand (Decision #27): 4k7, 1k5, 3k9
    - Symbolic strings: "2 * R1"
    """
    if raw is None:
        return None

    if isinstance(raw, (int, float)):
        return ParsedValue(raw=str(raw), numeric=float(raw), is_symbolic=False)

    val_str = str(raw).strip()

    # Fatal check on comma as decimal separator (Decision #17)
    if "," in val_str:
        # Check if comma looks like a decimal separator (e.g. 4,7 or 0,7)
        if re.search(r"\d+,\d+", val_str):
            raise CemlParseError(
                f"Comma ',' is not accepted as a decimal separator in '{val_str}'. Use '.' instead (Decision #17)."
            )

    # 1. Check resistor-style shorthand (e.g. 4k7 -> 4.7 * 1000 = 4700)
    match_short = RE_SHORTHAND.match(val_str)
    if match_short:
        base, suffix, frac = match_short.groups()
        num_str = f"{base}.{frac}"
        mult = MAGNITUDE_SUFFIXES[suffix]
        return ParsedValue(
            raw=val_str,
            numeric=float(num_str) * mult,
            is_symbolic=False,
            unit=suffix,
        )

    # 2. Check standard suffix notation (e.g. 4.7k, 10n)
    match_suffix = RE_STANDARD_SUFFIX.match(val_str)
    if match_suffix:
        num_str, suffix = match_suffix.groups()
        mult = MAGNITUDE_SUFFIXES[suffix]
        return ParsedValue(
            raw=val_str,
            numeric=float(num_str) * mult,
            is_symbolic=False,
            unit=suffix,
        )

    # 3. Check bare numeric float or int
    match_bare = RE_BARE_NUMBER.match(val_str)
    if match_bare:
        return ParsedValue(
            raw=val_str,
            numeric=float(match_bare.group(1)),
            is_symbolic=False,
        )

    # 4. Otherwise treated as symbolic expression or string parameter (e.g. '2 * R1' or 'ignored')
    return ParsedValue(
        raw=val_str,
        numeric=None,
        is_symbolic=True,
    )


def parse_function_call(raw: str) -> Union[FunctionCall, str]:
    """Parses a target string into a FunctionCall if parenthesized, or returns the bare string."""
    raw_clean = raw.strip()
    match = RE_FUNCTION_CALL.match(raw_clean)
    if not match:
        return raw_clean

    func_name, args_body = match.groups()
    raw_args = [arg.strip() for arg in args_body.split(",") if arg.strip()] if args_body.strip() else []

    has_hf = False
    args: list[str] = []
    for arg in raw_args:
        if arg == "hf":
            has_hf = True
        else:
            args.append(arg)

    return FunctionCall(name=func_name, args=args, has_hf=has_hf, raw=raw_clean)


def parse_node(data: dict[str, Any]) -> Node:
    """Parses a node definition from YAML dict."""
    if not isinstance(data, dict):
        raise CemlParseError(f"Node entry must be a dictionary, got {type(data).__name__}: {data}")

    if "id" not in data:
        raise CemlParseError(f"Node entry missing required 'id' field: {data}")

    node_id = str(data["id"])
    node_type_str = data.get("type", "internal")

    try:
        node_type = NodeType(node_type_str)
    except ValueError:
        # Keep string or invalid enum for validator to catch as fatal error
        node_type = NodeType.INTERNAL

    node_value = parse_engineering_value(data.get("value"))

    return Node(
        id=node_id,
        type=node_type,
        value=node_value,
        raw_data=data,
    )


def parse_component(data: dict[str, Any]) -> Component:
    """Parses a component definition from YAML dict."""
    if not isinstance(data, dict):
        raise CemlParseError(f"Component entry must be a dictionary, got {type(data).__name__}: {data}")

    if "id" not in data:
        raise CemlParseError(f"Component entry missing required 'id' field: {data}")

    comp_id = str(data["id"])
    comp_type = str(data.get("type", ""))

    pins_data = data.get("pins", [])
    if isinstance(pins_data, list):
        pins: Union[list[str], dict[str, str]] = [str(p) for p in pins_data]
    elif isinstance(pins_data, dict):
        pins = {str(k): str(v) for k, v in pins_data.items()}
    else:
        pins = []

    comp_value = parse_engineering_value(data.get("value"))

    role = data.get("role")
    model = data.get("model")

    ac_behavior_val = data.get("ac_behavior")
    ac_behavior: Optional[AcBehavior] = None
    if ac_behavior_val:
        try:
            ac_behavior = AcBehavior(ac_behavior_val)
        except ValueError:
            pass

    polarized = data.get("polarized")
    if polarized is not None:
        polarized = bool(polarized)

    regime_val = data.get("regime")
    regime: Optional[Regime] = None
    if regime_val:
        try:
            regime = Regime(regime_val)
        except ValueError:
            pass

    polarity_val = data.get("polarity")
    polarity: Optional[Polarity] = None
    if polarity_val:
        try:
            polarity = Polarity(polarity_val)
        except ValueError:
            pass

    rms = data.get("rms")
    if rms is not None:
        rms = bool(rms)

    phase_raw = data.get("phase")
    phase = float(phase_raw) if phase_raw is not None else None

    gain = data.get("gain")

    control_data = data.get("control")
    control: Optional[DependentControl] = None
    if isinstance(control_data, dict):
        c_type = str(control_data.get("type", ""))
        c_pins = [str(p) for p in control_data.get("pins", [])]
        control = DependentControl(type=c_type, pins=c_pins)

    return Component(
        id=comp_id,
        type=comp_type,
        pins=pins,
        value=comp_value,
        role=role,
        model=model,
        ac_behavior=ac_behavior,
        polarized=polarized,
        regime=regime,
        polarity=polarity,
        rms=rms,
        phase=phase,
        gain=gain,
        control=control,
        raw_data=data,
    )


def parse_specs(data: Any) -> Optional[Specs]:
    """Parses specs section containing given and find."""
    if data is None:
        return None

    if not isinstance(data, dict):
        return Specs()

    given_items: list[SpecItem] = []
    given_data = data.get("given")
    if isinstance(given_data, list):
        for item in given_data:
            if isinstance(item, dict):
                for k, v in item.items():
                    target = parse_function_call(str(k))
                    parsed_val = parse_engineering_value(v)
                    given_items.append(SpecItem(target=target, value=parsed_val, raw=f"{k}: {v}"))
            elif isinstance(item, str):
                target = parse_function_call(item)
                given_items.append(SpecItem(target=target, value=None, raw=item))

    find_items: list[SpecItem] = []
    find_data = data.get("find")
    if isinstance(find_data, list):
        for item in find_data:
            if isinstance(item, str):
                target = parse_function_call(item)
                find_items.append(SpecItem(target=target, value=None, raw=item))
            elif isinstance(item, dict):
                for k, v in item.items():
                    target = parse_function_call(str(k))
                    parsed_val = parse_engineering_value(v)
                    find_items.append(SpecItem(target=target, value=parsed_val, raw=f"{k}: {v}"))

    return Specs(given=given_items, find=find_items)


def loads(text: str) -> Circuit:
    """Parses a CEML specification string into a Circuit AST."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CemlParseError(f"YAML syntax error: {exc}") from exc

    if not isinstance(data, dict):
        raise CemlParseError(f"Expected top-level YAML mapping, got {type(data).__name__}")

    ceml_version = str(data.get("ceml_version", ""))
    circuit_id = str(data.get("circuit_id", ""))
    description = data.get("description")

    # Parse nodes
    nodes: dict[str, Node] = {}
    nodes_data = data.get("nodes")
    if isinstance(nodes_data, list):
        for entry in nodes_data:
            node = parse_node(entry)
            nodes[node.id] = node

    # Parse components
    components: dict[str, Component] = {}
    comps_data = data.get("components")
    if isinstance(comps_data, list):
        for entry in comps_data:
            comp = parse_component(entry)
            components[comp.id] = comp

    # Parse specs
    specs = parse_specs(data.get("specs"))

    return Circuit(
        ceml_version=ceml_version,
        circuit_id=circuit_id,
        description=description,
        nodes=nodes,
        components=components,
        specs=specs,
        raw_data=data,
    )


def load(path: Union[str, Path]) -> Circuit:
    """Parses a CEML .ci file into a Circuit AST."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"CEML file not found: {p}")

    content = p.read_text(encoding="utf-8")
    return loads(content)
