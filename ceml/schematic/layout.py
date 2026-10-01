"""Schematic Layout Engine for CEML circuits.

Computes 2D placement coordinates, stage sequences, and wire connections
following canonical analog electronic drafting conventions (left-to-right signal flow,
power rail on top, ground on bottom, vertical transistor alignment).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Union

from ceml.models import Circuit, Component, ComponentType, Node, NodeType


@dataclass
class StageLayout:
    """Stores geometric layout coordinates and assigned components for an amplifier stage."""
    stage_index: int
    transistor: Component
    is_bjt: bool
    is_nmos: bool
    is_pnp: bool
    base_gate_node: str
    collector_drain_node: str
    emitter_source_node: str
    input_pin_name: str = "base"  # "base", "gate", "emitter", "source"
    output_pin_name: str = "collector"  # "collector", "drain", "emitter", "source"
    input_chain: list[Component] = field(default_factory=list)
    output_chain: list[Component] = field(default_factory=list)
    base_gate_pullup: list[Component] = field(default_factory=list)
    base_gate_pulldown: list[Component] = field(default_factory=list)
    base_gate_bypass: list[Component] = field(default_factory=list)
    collector_drain_pullup: list[Component] = field(default_factory=list)
    collector_drain_pulldown: list[Component] = field(default_factory=list)
    emitter_source_pulldown: list[Component] = field(default_factory=list)
    emitter_source_bypass: list[list[Component]] = field(default_factory=list)
    load_components: list[Component] = field(default_factory=list)
    x_stage: float = 5.0
    x_bias: float = 3.0

    y_mid: float = 3.0
    y_top: float = 6.0
    y_bot: float = 0.0


@dataclass
class CircuitLayoutPlan:
    """Overall layout plan for the schematic drawing."""
    circuit_id: str
    is_active_amplifier: bool
    stages: list[StageLayout] = field(default_factory=list)
    passive_chain: list[Component] = field(default_factory=list)
    supply_node_id: str = "VCC"
    ground_node_id: str = "GND"
    input_node_id: Optional[str] = None
    output_node_id: Optional[str] = None
    width: float = 10.0
    height: float = 7.0


def _get_pins(c: Component) -> list[str]:
    """Helper returning pin list for any component."""
    if isinstance(c.pins, list):
        return c.pins
    return list(c.pins.values())


def _trace_chain(
    circuit: Circuit,
    start_node: str,
    stop_nodes: set[str],
) -> tuple[list[Component], str, Optional[Component]]:
    """Traces a series 2-pin component chain from start_node until an active device or stop node is hit."""
    chain: list[Component] = []
    curr = start_node
    visited = {start_node} | stop_nodes

    while True:
        # Check if curr is attached to a transistor
        trans = [
            c for c in circuit.components.values()
            if c.type in (ComponentType.BJT, ComponentType.MOSFET, ComponentType.JFET)
            and curr in _get_pins(c)
        ]
        if trans:
            return chain, curr, trans[0]

        next_comps = [
            c for c in circuit.components.values()
            if c.type in (ComponentType.RESISTOR, ComponentType.CAPACITOR, ComponentType.INDUCTOR)
            and curr in _get_pins(c)
        ]
        found = False
        for c in next_comps:
            pins = _get_pins(c)
            other = pins[1] if pins[0] == curr else pins[0]
            if other not in visited:
                chain.append(c)
                visited.add(other)
                curr = other
                found = True
                break
        if not found:
            break

    return chain, curr, None


def plan_circuit_layout(circuit: Circuit) -> CircuitLayoutPlan:
    """Analyzes a Circuit AST and formulates a 2D layout plan."""
    # 1. Identify canonical power, ground, and I/O nodes
    supply_nodes = {
        n.id for n in circuit.nodes.values()
        if n.type == NodeType.SUPPLY or n.id in ("VCC", "VDD", "VEE")
    }
    ground_nodes = {
        n.id for n in circuit.nodes.values()
        if n.type == NodeType.GROUND or n.id in ("GND", "0")
    }
    input_nodes = [
        n.id for n in circuit.nodes.values()
        if n.type == NodeType.INPUT or n.id in ("Vin", "Vs", "IN")
    ]
    output_nodes = [
        n.id for n in circuit.nodes.values()
        if n.type == NodeType.OUTPUT or n.id in ("Vout", "OUT")
    ]

    v_sup = next(iter(supply_nodes)) if supply_nodes else "VCC"
    gnd = next(iter(ground_nodes)) if ground_nodes else "GND"
    v_in = input_nodes[0] if input_nodes else None
    v_out = output_nodes[0] if output_nodes else None

    # 2. Identify active semiconductor devices
    transistors = [
        c for c in circuit.components.values()
        if c.type in (ComponentType.BJT, ComponentType.MOSFET, ComponentType.JFET)
    ]

    if not transistors:
        return _plan_passive_circuit(circuit, v_sup, gnd, v_in, v_out)

    # 3. Trace input chain from v_in
    input_chain: list[Component] = []
    input_target_node = ""
    first_transistor: Optional[Component] = None

    if v_in:
        stop_set = ground_nodes | supply_nodes
        input_chain, input_target_node, first_transistor = _trace_chain(circuit, v_in, stop_set)

    # 4. Trace output chain from v_out
    output_chain: list[Component] = []
    output_source_node = ""
    last_transistor: Optional[Component] = None

    if v_out:
        stop_set = ground_nodes | supply_nodes
        output_chain, output_source_node, last_transistor = _trace_chain(circuit, v_out, stop_set)
        # Reversed so chain goes from transistor towards v_out
        output_chain.reverse()

    # Map components by node
    components_by_node: dict[str, list[Component]] = {}
    for c in circuit.components.values():
        for p in _get_pins(c):
            components_by_node.setdefault(p, []).append(c)

    stages: list[StageLayout] = []
    x_cursor = 1.0

    for idx, q in enumerate(transistors):
        is_bjt = q.type == ComponentType.BJT
        is_nmos = q.type == ComponentType.MOSFET and getattr(q, "polarity", "NMOS") == "NMOS"
        is_pnp = is_bjt and getattr(q, "polarity", "NPN") == "PNP"

        pins = q.pins if isinstance(q.pins, dict) else {}
        if is_bjt:
            base_node = pins.get("base", "")
            coll_node = pins.get("collector", "")
            emit_node = pins.get("emitter", "")
        else:
            base_node = pins.get("gate", "")
            coll_node = pins.get("drain", "")
            emit_node = pins.get("source", "")

        # Detect input pin
        if input_target_node == emit_node:
            input_pin = "emitter" if is_bjt else "source"
        else:
            input_pin = "base" if is_bjt else "gate"

        # Detect output pin
        if output_source_node == emit_node:
            output_pin = "emitter" if is_bjt else "source"
        else:
            output_pin = "collector" if is_bjt else "drain"

        is_cb_cg = input_pin in ("emitter", "source")
        if is_cb_cg:
            in_len = len(input_chain) if idx == 0 and input_chain else 1
            x_bias = x_cursor + 2.0
            x_stage = x_bias + max(4.5, in_len * 2.2 + 1.8)
        else:
            x_bias = x_cursor + 2.5
            x_stage = x_bias + 3.2

        stage = StageLayout(
            stage_index=idx,
            transistor=q,
            is_bjt=is_bjt,
            is_nmos=is_nmos,
            is_pnp=is_pnp,
            base_gate_node=base_node,
            collector_drain_node=coll_node,
            emitter_source_node=emit_node,
            input_pin_name=input_pin,
            output_pin_name=output_pin,
            x_stage=x_stage,
            x_bias=x_bias,
        )

        if idx == 0 and input_chain:
            stage.input_chain = input_chain

        if idx == len(transistors) - 1 and output_chain:
            stage.output_chain = output_chain

        # Inspect Base/Gate node components
        for c in components_by_node.get(base_node, []):
            if c.id == q.id or c in input_chain or c in output_chain:
                continue
            cpins = _get_pins(c)
            if any(s in supply_nodes for s in cpins):
                stage.base_gate_pullup.append(c)
            elif any(g in ground_nodes for g in cpins):
                if c.type == ComponentType.CAPACITOR:
                    stage.base_gate_bypass.append(c)
                else:
                    stage.base_gate_pulldown.append(c)

        # Inspect Collector/Drain node components
        for c in components_by_node.get(coll_node, []):
            if c.id == q.id or c in input_chain or c in output_chain:
                continue
            cpins = _get_pins(c)
            if any(s in supply_nodes for s in cpins):
                stage.collector_drain_pullup.append(c)
            elif any(g in ground_nodes for g in cpins):
                stage.collector_drain_pulldown.append(c)

        # Inspect Emitter/Source node components
        for c in components_by_node.get(emit_node, []):
            if c.id == q.id or c in input_chain or c in output_chain:
                continue
            cpins = _get_pins(c)
            if any(g in ground_nodes for g in cpins):
                if c.type == ComponentType.CAPACITOR:
                    stage.emitter_source_bypass.append([c])
                else:
                    stage.emitter_source_pulldown.append(c)
            else:
                # Intermediate node (e.g. N4 for partial bypass C3 + R1)
                other_pin = cpins[1] if cpins[0] == emit_node else cpins[0]
                branch_comps = [c]
                curr_p = other_pin
                while curr_p not in ground_nodes:
                    next_c = [
                        nxt for nxt in components_by_node.get(curr_p, [])
                        if nxt not in branch_comps and nxt.id != q.id
                    ]
                    if not next_c:
                        break
                    branch_comps.append(next_c[0])
                    npins = _get_pins(next_c[0])
                    curr_p = npins[1] if npins[0] == curr_p else npins[0]
                if curr_p in ground_nodes:
                    stage.emitter_source_bypass.append(branch_comps)


        # Load components at v_out
        if idx == len(transistors) - 1 and v_out:
            for c in components_by_node.get(v_out, []):
                if c in output_chain:
                    continue
                cpins = _get_pins(c)
                if any(g in ground_nodes for g in cpins):
                    stage.load_components.append(c)

        stages.append(stage)
        x_cursor = x_stage + 3.0

    total_width = x_cursor + 2.0

    return CircuitLayoutPlan(
        circuit_id=circuit.circuit_id,
        is_active_amplifier=True,
        stages=stages,
        supply_node_id=v_sup,
        ground_node_id=gnd,
        input_node_id=v_in,
        output_node_id=v_out,
        width=total_width,
        height=7.0,
    )


def _plan_passive_circuit(
    circuit: Circuit,
    v_sup: str,
    gnd: str,
    v_in: Optional[str],
    v_out: Optional[str],
) -> CircuitLayoutPlan:
    """Plans layout for a passive / loop circuit without active semiconductors."""
    passive_components = list(circuit.components.values())
    return CircuitLayoutPlan(
        circuit_id=circuit.circuit_id,
        is_active_amplifier=False,
        passive_chain=passive_components,
        supply_node_id=v_sup,
        ground_node_id=gnd,
        input_node_id=v_in,
        output_node_id=v_out,
        width=len(passive_components) * 2.0 + 2.0,
        height=5.0,
    )
