"""CEML Validator.

Implements semantic and topological validation rules from CEML Specification v0.1 (§9).
Detects fatal errors, warnings, and suggestions.
"""

from __future__ import annotations

from typing import Optional, Set

from ceml.models import (
    AcBehavior,
    Circuit,
    Component,
    ComponentType,
    FunctionCall,
    Node,
    NodeType,
    Polarity,
    Regime,
    SpecItem,
    ValidationError,
    ValidationResult,
    ValidationSuggestion,
    ValidationWarning,
)

# Reserved words and functions (§8)
RESERVED_MEASUREMENT = {"Vdc", "Vac", "Idc", "Iac", "Z"}
RESERVED_BEHAVIORAL = {"Av", "Ai", "Rin", "Rout", "Zin", "Zout", "Zt", "Yt"}
RESERVED_TRANSISTOR = {
    "Vbe", "Vce", "Vbc", "Vgs", "Vds", "Vgd",
    "Ic", "Ib", "Ie", "Id", "Ig", "Is",
    "hfe", "Cpi", "Cmu", "hie", "hoe", "hre",
}
RESERVED_TWO_PORT = {"Zparam", "Yparam", "Hparam", "Gparam", "ABCD"}
RESERVED_SPECIAL = {"Commercial", "Expr"}

ALL_RESERVED_FUNCTIONS = (
    RESERVED_MEASUREMENT
    | RESERVED_BEHAVIORAL
    | RESERVED_TRANSISTOR
    | RESERVED_TWO_PORT
    | RESERVED_SPECIAL
)

RESERVED_WORDS = ALL_RESERVED_FUNCTIONS | {"GND"}

HF_ALLOWED_FUNCTIONS = {"Vac", "Iac", "Z"} | RESERVED_BEHAVIORAL

VALID_NODE_TYPES = {t.value for t in NodeType}

VALID_COMPONENT_TYPES = {t.value for t in ComponentType}

VALID_COMMERCIAL_MODES = {"min", "max", "nearest"}
VALID_COMMERCIAL_SERIES = {"E12", "E24", "E48", "E96"}


class CemlValidationError(Exception):
    """Exception raised when fatal errors are found and strict mode is active."""

    def __init__(self, errors: list[ValidationError]):
        self.errors = errors
        msg = f"Circuit validation failed with {len(errors)} fatal error(s):\n" + "\n".join(
            f"  - [{e.code}] {e.message}" for e in errors
        )
        super().__init__(msg)


def _extract_find_targets(find_items: list[SpecItem]) -> Set[str]:
    """Extracts component or parameter identifiers targeted in specs.find."""
    targets: Set[str] = set()
    for item in find_items:
        if isinstance(item.target, str):
            targets.add(item.target)
        elif isinstance(item.target, FunctionCall):
            fn = item.target
            if fn.name == "Commercial" and fn.args:
                targets.add(fn.args[0])
            elif fn.name in ("Idc", "Iac") and len(fn.args) == 1:
                targets.add(fn.args[0])
            elif fn.name in RESERVED_TRANSISTOR and fn.args:
                targets.add(fn.args[0])
    return targets


def _extract_given_targets(given_items: list[SpecItem]) -> Set[str]:
    """Extracts target signatures from specs.given."""
    targets: Set[str] = set()
    for item in given_items:
        if isinstance(item.target, str):
            targets.add(item.target)
        elif isinstance(item.target, FunctionCall):
            targets.add(item.target.raw)
    return targets


def validate(circuit: Circuit, strict: bool = False) -> ValidationResult:
    """Validates a Circuit according to CEML v0.1 specification (§9).

    Args:
        circuit: The Circuit AST to validate.
        strict: If True, raises CemlValidationError if any fatal error is detected.

    Returns:
        ValidationResult with errors, warnings, and suggestions.
    """
    errors: list[ValidationError] = []
    warnings: list[ValidationWarning] = []
    suggestions: list[ValidationSuggestion] = []

    raw_nodes = circuit.raw_data.get("nodes") or []
    raw_components = circuit.raw_data.get("components") or []

    # -------------------------------------------------------------
    # 1. FATAL ERROR: Duplicate IDs & Node validity
    # -------------------------------------------------------------
    seen_node_ids: set[str] = set()
    for n in raw_nodes:
        if isinstance(n, dict) and "id" in n:
            nid = str(n["id"])
            if nid in seen_node_ids:
                errors.append(
                    ValidationError(
                        code="ERR_DUPLICATE_NODE_ID",
                        message=f"Duplicate node ID '{nid}' found.",
                        node_id=nid,
                    )
                )
            seen_node_ids.add(nid)

    seen_comp_ids: set[str] = set()
    for c in raw_components:
        if isinstance(c, dict) and "id" in c:
            cid = str(c["id"])
            if cid in seen_comp_ids:
                errors.append(
                    ValidationError(
                        code="ERR_DUPLICATE_COMPONENT_ID",
                        message=f"Duplicate component ID '{cid}' found.",
                        component_id=cid,
                    )
                )
            if cid in seen_node_ids:
                errors.append(
                    ValidationError(
                        code="ERR_ID_COLLISION",
                        message=f"ID '{cid}' used for both a component and a node.",
                        component_id=cid,
                    )
                )
            seen_comp_ids.add(cid)

    # Validate raw node types
    for n in raw_nodes:
        if isinstance(n, dict):
            t = n.get("type")
            if t is not None and t not in VALID_NODE_TYPES:
                errors.append(
                    ValidationError(
                        code="ERR_INVALID_NODE_TYPE",
                        message=f"Node '{n.get('id')}' has invalid type '{t}'. Must be one of {sorted(VALID_NODE_TYPES)}.",
                        node_id=str(n.get("id")),
                    )
                )

    # -------------------------------------------------------------
    # 2. FATAL ERROR: Ground node existence (§3, §9)
    # -------------------------------------------------------------
    has_ground = any(node.type == NodeType.GROUND for node in circuit.nodes.values())
    if not has_ground:
        errors.append(
            ValidationError(
                code="ERR_NO_GROUND",
                message="Every circuit must have at least one 'ground' node declared.",
            )
        )

    # Track node connections to detect unconnected nodes later
    connected_nodes: set[str] = set()

    # Find targets for component value checks
    find_targets = _extract_find_targets(circuit.specs.find) if circuit.specs else set()

    # -------------------------------------------------------------
    # 3. Component Validation
    # -------------------------------------------------------------
    for comp in circuit.components.values():
        comp_nodes = comp.get_connected_nodes()
        connected_nodes.update(comp_nodes)

        # Fatal: Invalid component type
        if comp.type not in VALID_COMPONENT_TYPES:
            errors.append(
                ValidationError(
                    code="ERR_INVALID_COMPONENT_TYPE",
                    message=f"Component '{comp.id}' has invalid or unsupported type '{comp.type}'.",
                    component_id=comp.id,
                )
            )

        # Fatal: Undeclared node reference
        for node_ref in comp_nodes:
            if node_ref not in circuit.nodes:
                errors.append(
                    ValidationError(
                        code="ERR_UNDECLARED_NODE",
                        message=f"Component '{comp.id}' references undeclared node '{node_ref}'.",
                        component_id=comp.id,
                        node_id=node_ref,
                    )
                )

        # Fatal: Polarized check on passives (§4, §5, §9)
        if comp.type in (ComponentType.RESISTOR.value, ComponentType.INDUCTOR.value):
            if comp.polarized is True:
                errors.append(
                    ValidationError(
                        code="ERR_INVALID_POLARIZATION",
                        message=f"'polarized: true' is invalid for component '{comp.id}' of type '{comp.type}'.",
                        component_id=comp.id,
                    )
                )

        # Fatal: Pinout checks (§5, §9)
        if comp.type in (ComponentType.RESISTOR.value, ComponentType.CAPACITOR.value, ComponentType.INDUCTOR.value):
            if comp.polarized is True:
                if not isinstance(comp.pins, dict) or "p" not in comp.pins or "n" not in comp.pins:
                    errors.append(
                        ValidationError(
                            code="ERR_MISSING_POLARIZED_PINS",
                            message=f"Polarized component '{comp.id}' must declare 'p' and 'n' pin terminals.",
                            component_id=comp.id,
                        )
                    )
            else:
                if isinstance(comp.pins, list) and len(comp.pins) != 2:
                    errors.append(
                        ValidationError(
                            code="ERR_INVALID_PIN_COUNT",
                            message=f"Passive component '{comp.id}' requires exactly 2 pins, got {len(comp.pins)}.",
                            component_id=comp.id,
                        )
                    )

        elif comp.type in (ComponentType.VOLTAGE_SOURCE.value, ComponentType.CURRENT_SOURCE.value, ComponentType.DIODE.value):
            if not isinstance(comp.pins, dict) or "p" not in comp.pins or "n" not in comp.pins:
                errors.append(
                    ValidationError(
                        code="ERR_MISSING_PN_PINS",
                        message=f"Component '{comp.id}' of type '{comp.type}' must define 'p' and 'n' pin terminals.",
                        component_id=comp.id,
                    )
                )

        elif comp.type == ComponentType.BJT.value:
            if not isinstance(comp.pins, dict) or not {"base", "collector", "emitter"}.issubset(comp.pins.keys()):
                errors.append(
                    ValidationError(
                        code="ERR_MISSING_BJT_PINS",
                        message=f"BJT '{comp.id}' requires 'base', 'collector', and 'emitter' pin terminals.",
                        component_id=comp.id,
                    )
                )

        elif comp.type in (ComponentType.MOSFET.value, ComponentType.JFET.value):
            if not isinstance(comp.pins, dict) or not {"gate", "drain", "source"}.issubset(comp.pins.keys()):
                errors.append(
                    ValidationError(
                        code="ERR_MISSING_FET_PINS",
                        message=f"Transistor '{comp.id}' requires 'gate', 'drain', and 'source' pin terminals.",
                        component_id=comp.id,
                    )
                )

        elif comp.type == ComponentType.OPAMP.value:
            if not isinstance(comp.pins, dict) or not {"in+", "in-", "out"}.issubset(comp.pins.keys()):
                errors.append(
                    ValidationError(
                        code="ERR_MISSING_OPAMP_PINS",
                        message=f"OpAmp '{comp.id}' requires 'in+', 'in-', and 'out' pin terminals.",
                        component_id=comp.id,
                    )
                )

        elif comp.type in (ComponentType.VCVS.value, ComponentType.VCCS.value, ComponentType.CCVS.value, ComponentType.CCCS.value):
            if not isinstance(comp.pins, list) or len(comp.pins) != 2:
                errors.append(
                    ValidationError(
                        code="ERR_MISSING_DEPENDENT_PINS",
                        message=f"Dependent source '{comp.id}' requires 2 physical pins.",
                        component_id=comp.id,
                    )
                )
            if not comp.control or not comp.control.pins or len(comp.control.pins) != 2:
                errors.append(
                    ValidationError(
                        code="ERR_MISSING_CONTROL_BLOCK",
                        message=f"Dependent source '{comp.id}' requires control block with 2 measurement pins.",
                        component_id=comp.id,
                    )
                )

        # Fatal: Source regime (§4, §9)
        if comp.type in (ComponentType.VOLTAGE_SOURCE.value, ComponentType.CURRENT_SOURCE.value):
            raw_regime = comp.raw_data.get("regime")
            if raw_regime not in ("DC", "AC"):
                errors.append(
                    ValidationError(
                        code="ERR_INVALID_SOURCE_REGIME",
                        message=f"Source '{comp.id}' must declare 'regime: DC' or 'regime: AC'.",
                        component_id=comp.id,
                    )
                )
            if comp.regime == Regime.DC:
                if comp.rms is not None or comp.phase is not None:
                    errors.append(
                        ValidationError(
                            code="ERR_DC_SOURCE_AC_FIELDS",
                            message=f"'rms' and 'phase' are invalid on 'regime: DC' source '{comp.id}'.",
                            component_id=comp.id,
                        )
                    )

        # Fatal: Polarity validity (§4, §9)
        raw_pol = comp.raw_data.get("polarity")
        if raw_pol is not None:
            if comp.type == ComponentType.BJT.value and raw_pol not in ("NPN", "PNP"):
                errors.append(
                    ValidationError(
                        code="ERR_INVALID_POLARITY",
                        message=f"Invalid polarity '{raw_pol}' for BJT '{comp.id}'. Must be NPN or PNP.",
                        component_id=comp.id,
                    )
                )
            elif comp.type == ComponentType.MOSFET.value and raw_pol not in ("NMOS", "PMOS"):
                errors.append(
                    ValidationError(
                        code="ERR_INVALID_POLARITY",
                        message=f"Invalid polarity '{raw_pol}' for MOSFET '{comp.id}'. Must be NMOS or PMOS.",
                        component_id=comp.id,
                    )
                )
            elif comp.type == ComponentType.JFET.value and raw_pol not in ("N", "P"):
                errors.append(
                    ValidationError(
                        code="ERR_INVALID_POLARITY",
                        message=f"Invalid polarity '{raw_pol}' for JFET '{comp.id}'. Must be N or P.",
                        component_id=comp.id,
                    )
                )

        # Fatal: Value absent from component not listed in find (§4, §9, Decision #3, #14)
        types_requiring_value = {
            ComponentType.RESISTOR.value,
            ComponentType.CAPACITOR.value,
            ComponentType.INDUCTOR.value,
            ComponentType.VOLTAGE_SOURCE.value,
            ComponentType.CURRENT_SOURCE.value,
        }
        if comp.type in types_requiring_value:
            has_val = comp.value is not None
            has_ac_beh = comp.ac_behavior is not None
            in_find = comp.id in find_targets
            if not has_val and not has_ac_beh and not in_find:
                errors.append(
                    ValidationError(
                        code="ERR_MISSING_VALUE_NOT_IN_FIND",
                        message=(
                            f"Component '{comp.id}' ({comp.type}) has no 'value', has no 'ac_behavior', "
                            f"and is not listed in specs.find."
                        ),
                        component_id=comp.id,
                    )
                )

        # Warnings on components (§6, §9)
        if comp.type == ComponentType.BJT.value:
            if comp.polarity is None:
                warnings.append(
                    ValidationWarning(
                        code="WARN_DEFAULT_POLARITY",
                        message=f"Polarity omitted on BJT '{comp.id}'. Defaulting to NPN (Decision #21).",
                        component_id=comp.id,
                    )
                )
            # VA absent check
            has_va = False
            has_hoe = False
            has_hfe = False
            has_cpi = False
            has_hre = False

            if circuit.specs and circuit.specs.given:
                for item in circuit.specs.given:
                    raw_str = item.raw
                    if f"hfe({comp.id})" in raw_str:
                        has_hfe = True
                    if f"Cpi({comp.id})" in raw_str or f"Cmu({comp.id})" in raw_str:
                        has_cpi = True
                    if f"hoe({comp.id})" in raw_str:
                        has_hoe = True
                    if f"hre({comp.id})" in raw_str:
                        has_hre = True
                    if "VA" in raw_str:
                        has_va = True

            if not has_hfe and not comp.model:
                warnings.append(
                    ValidationWarning(
                        code="WARN_DEFAULT_BJT_HFE",
                        message=f"hfe absent for BJT '{comp.id}'. Defaulting to 100 (Decision #1).",
                        component_id=comp.id,
                    )
                )
            if not has_va and not has_hoe and comp.raw_data.get("ro") != "ignored":
                warnings.append(
                    ValidationWarning(
                        code="WARN_DEFAULT_RO_INF",
                        message=f"VA / hoe absent for BJT '{comp.id}'. Assuming ro -> inf (Decision #2).",
                        component_id=comp.id,
                    )
                )
            if not has_cpi:
                warnings.append(
                    ValidationWarning(
                        code="WARN_HF_EFFECTS_IGNORED",
                        message=f"Cpi/Cmu absent for BJT '{comp.id}'. High-frequency effects ignored (Decision #22).",
                        component_id=comp.id,
                    )
                )
            if not has_hre:
                warnings.append(
                    ValidationWarning(
                        code="WARN_DEFAULT_HRE_ZERO",
                        message=f"hre absent for BJT '{comp.id}'. Assuming hre = 0 (Decision #24).",
                        component_id=comp.id,
                    )
                )

        elif comp.type in (ComponentType.MOSFET.value, ComponentType.JFET.value):
            if comp.polarity is None:
                def_pol = "NMOS" if comp.type == ComponentType.MOSFET.value else "N"
                warnings.append(
                    ValidationWarning(
                        code="WARN_DEFAULT_POLARITY",
                        message=f"Polarity omitted on {comp.type} '{comp.id}'. Defaulting to {def_pol} (Decision #21).",
                        component_id=comp.id,
                    )
                )

        elif comp.type == ComponentType.OPAMP.value:
            if isinstance(comp.pins, dict):
                if "vcc" not in comp.pins and "vee" not in comp.pins:
                    warnings.append(
                        ValidationWarning(
                            code="WARN_IDEAL_OPAMP_SUPPLY",
                            message=f"vcc/vee omitted on opamp '{comp.id}'. Assuming ideal supply.",
                            component_id=comp.id,
                        )
                    )

        # Suggestion: Missing role
        if not comp.role:
            suggestions.append(
                ValidationSuggestion(
                    code="SUGG_MISSING_ROLE",
                    message=f"Component '{comp.id}' has no 'role' field. Adding semantic context is recommended.",
                    component_id=comp.id,
                )
            )

    # -------------------------------------------------------------
    # 4. Warnings on Nodes (§9)
    # -------------------------------------------------------------
    # Node declared but not connected to any component
    for node_id in circuit.nodes:
        if node_id not in connected_nodes:
            warnings.append(
                ValidationWarning(
                    code="WARN_UNCONNECTED_NODE",
                    message=f"Node '{node_id}' is declared but not connected to any component.",
                    node_id=node_id,
                )
            )

    # No input or output node declared
    has_in_or_out = any(
        node.type in (NodeType.INPUT, NodeType.OUTPUT, NodeType.BIDIR)
        for node in circuit.nodes.values()
    )
    if not has_in_or_out:
        warnings.append(
            ValidationWarning(
                code="WARN_NO_IN_OUT_NODE",
                message="No 'input', 'output', or 'bidir' node declared in circuit.",
            )
        )

    # -------------------------------------------------------------
    # 5. Specs & Reserved Functions Validation (§8, §9)
    # -------------------------------------------------------------
    if not circuit.specs or (not circuit.specs.given and not circuit.specs.find):
        suggestions.append(
            ValidationSuggestion(
                code="SUGG_MISSING_SPECS",
                message="Circuit has no 'specs' section or both 'given' and 'find' are empty.",
            )
        )
    else:
        # Validate 'given'
        for item in circuit.specs.given:
            if isinstance(item.target, FunctionCall):
                fn = item.target
                _validate_function_call(fn, is_find=False, circuit=circuit, errors=errors)
            elif isinstance(item.target, str):
                pass

        # Validate 'find'
        for item in circuit.specs.find:
            if isinstance(item.target, str):
                # Fatal: Free names in find cannot match any reserved word or function
                if item.target in RESERVED_WORDS:
                    errors.append(
                        ValidationError(
                            code="ERR_RESERVED_WORD_AS_FREE_NAME",
                            message=f"Reserved word or function '{item.target}' used as a free name in find without parameters.",
                        )
                    )
            elif isinstance(item.target, FunctionCall):
                fn = item.target
                _validate_function_call(fn, is_find=True, circuit=circuit, errors=errors)

    if strict and errors:
        raise CemlValidationError(errors)

    return ValidationResult(
        errors=errors,
        warnings=warnings,
        suggestions=suggestions,
    )


def _validate_function_call(
    fn: FunctionCall,
    is_find: bool,
    circuit: Circuit,
    errors: list[ValidationError],
) -> None:
    """Validates function arity, parameter rules, and frequency band legality."""
    # 1. Check if known reserved function
    if fn.name not in ALL_RESERVED_FUNCTIONS:
        return

    # 2. Fatal: Mandatory parameters check
    if not fn.args and not fn.has_hf:
        errors.append(
            ValidationError(
                code="ERR_MISSING_FUNCTION_ARGS",
                message=f"Reserved function '{fn.name}' used without mandatory parameters.",
            )
        )
        return

    # 3. Fatal: 'hf' argument legality (§8, §9)
    if fn.has_hf and fn.name not in HF_ALLOWED_FUNCTIONS:
        errors.append(
            ValidationError(
                code="ERR_INVALID_HF_ARGUMENT",
                message=f"'hf' argument passed to function '{fn.name}', which has no frequency-dependent variant.",
            )
        )

    # 4. Fatal: Commercial and Expr rules
    if fn.name == "Commercial":
        if not is_find:
            errors.append(
                ValidationError(
                    code="ERR_COMMERCIAL_IN_GIVEN",
                    message="Commercial(...) function is only valid in 'find'.",
                )
            )
        if len(fn.args) < 1:
            errors.append(
                ValidationError(
                    code="ERR_COMMERCIAL_MISSING_COMPONENT",
                    message="Commercial(...) requires at least the component ID as argument.",
                )
            )

    elif fn.name == "Expr":
        if not is_find:
            errors.append(
                ValidationError(
                    code="ERR_EXPR_IN_GIVEN",
                    message="Expr(...) function is only valid in 'find'.",
                )
            )
        if len(fn.args) < 2:
            errors.append(
                ValidationError(
                    code="ERR_EXPR_ARITY",
                    message=f"Expr(...) requires at least a TARGET node and one VAR node (got {len(fn.args)}).",
                )
            )
        # Fatal: TARGET and every VAR must be declared and NOT ground or supply
        for node_ref in fn.args:
            node_obj = circuit.nodes.get(node_ref)
            if not node_obj:
                errors.append(
                    ValidationError(
                        code="ERR_EXPR_UNDECLARED_NODE",
                        message=f"Expr(...) references undeclared node '{node_ref}'.",
                        node_id=node_ref,
                    )
                )
            elif node_obj.type in (NodeType.GROUND, NodeType.SUPPLY):
                errors.append(
                    ValidationError(
                        code="ERR_EXPR_INVALID_NODE_TYPE",
                        message=(
                            f"Expr(...) cannot reference '{node_obj.type.value}' node '{node_ref}' "
                            f"as TARGET or VAR (must be input, output, internal, or bidir)."
                        ),
                        node_id=node_ref,
                    )
                )

    elif fn.name in RESERVED_TWO_PORT:
        if len(fn.args) != 2:
            errors.append(
                ValidationError(
                    code="ERR_TWO_PORT_ARITY",
                    message=f"Two-port function '{fn.name}' requires 2 port indices (got {len(fn.args)}).",
                )
            )
        else:
            for idx in fn.args:
                if idx not in ("1", "2"):
                    errors.append(
                        ValidationError(
                            code="ERR_TWO_PORT_INDEX",
                            message=f"Two-port index must be 1 or 2, got '{idx}' in '{fn.name}'.",
                        )
                    )
