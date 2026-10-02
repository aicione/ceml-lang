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
    direct_ties: dict[str, str] = field(default_factory=dict)  # pin_name -> rail_node_id
    base_gate_pullup: list[Component] = field(default_factory=list)
    base_gate_pulldown: list[Component] = field(default_factory=list)
    base_gate_bypass: list[Component] = field(default_factory=list)
    collector_drain_pullup: list[Component] = field(default_factory=list)
    collector_drain_pulldown: list[Component] = field(default_factory=list)
    emitter_source_pulldown: list[Component] = field(default_factory=list)
    emitter_source_pulldown_vee: list[Component] = field(default_factory=list)
    emitter_source_bypass: list[list[Component]] = field(default_factory=list)
    load_components: list[Component] = field(default_factory=list)
    load_components_vee: list[Component] = field(default_factory=list)
    is_tail_bias: bool = False
    host_transistor_id: Optional[str] = None
    x_stage: float = 5.0
    x_bias: float = 3.0
    y_trans: float = 5.5


@dataclass
class CircuitLayoutPlan:
    """Overall layout plan for the schematic drawing."""
    circuit_id: str
    is_active_amplifier: bool
    is_opamp_circuit: bool = False
    stages: list[StageLayout] = field(default_factory=list)
    tail_stages: list[StageLayout] = field(default_factory=list)
    bridge_components: list[Component] = field(default_factory=list)
    passive_chain: list[Component] = field(default_factory=list)
    opamps: list[Component] = field(default_factory=list)
    supply_node_id: str = "VCC"
    negative_supply_node_id: Optional[str] = None
    ground_node_id: str = "GND"
    pos_supply_nodes: set[str] = field(default_factory=set)
    neg_supply_nodes: set[str] = field(default_factory=set)
    ground_nodes: set[str] = field(default_factory=set)
    input_node_id: Optional[str] = None
    output_node_id: Optional[str] = None
    width: float = 12.0
    height: float = 8.0
    y_vcc: float = 8.5
    y_gnd: float = 0.5
    y_vee: float = 0.5
    y_fwd: float = 5.5
    y_fb: float = 2.2


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
    pos_supply_nodes = {
        n.id for n in circuit.nodes.values()
        if (n.type == NodeType.SUPPLY and (n.value is None or n.value.numeric is None or n.value.numeric > 0)
        and n.id not in ("VEE", "VSS", "-VCC", "-VDD"))
    } | ({"VCC", "VDD"} & set(circuit.nodes.keys()))

    neg_supply_nodes = {
        n.id for n in circuit.nodes.values()
        if (n.type == NodeType.SUPPLY and n.value and n.value.numeric is not None and n.value.numeric < 0)
        or n.id in ("VEE", "VSS", "-VCC", "-VDD")
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

    v_sup = next(iter(pos_supply_nodes)) if pos_supply_nodes else "VCC"
    v_neg = next(iter(neg_supply_nodes)) if neg_supply_nodes else None
    gnd = next(iter(ground_nodes)) if ground_nodes else "GND"
    v_in = input_nodes[0] if input_nodes else None
    v_out = output_nodes[0] if output_nodes else None

    # 2. Identify active semiconductor devices
    all_transistors = [
        c for c in circuit.components.values()
        if c.type in (ComponentType.BJT, ComponentType.MOSFET, ComponentType.JFET)
    ]
    all_trans_pins = set()
    for t in all_transistors:
        all_trans_pins.update(_get_pins(t))

    opamps = [
        c for c in circuit.components.values()
        if c.type == ComponentType.OPAMP
    ]

    if not all_transistors and opamps:
        return CircuitLayoutPlan(
            circuit_id=circuit.circuit_id,
            is_active_amplifier=False,
            is_opamp_circuit=True,
            opamps=opamps,
            supply_node_id=v_sup,
            ground_node_id=gnd,
            input_node_id=v_in,
            output_node_id=v_out,
            width=16.0,
            height=10.0,
        )

    if not all_transistors:
        return _plan_passive_circuit(circuit, v_sup, gnd, v_in, v_out)

    # 3. Trace input chain from v_in
    input_chain: list[Component] = []
    input_target_node = ""
    first_transistor: Optional[Component] = None

    if v_in:
        stop_set = ground_nodes | pos_supply_nodes | neg_supply_nodes
        input_chain, input_target_node, first_transistor = _trace_chain(circuit, v_in, stop_set)

    # 4. Trace output chain from v_out
    output_chain: list[Component] = []
    output_source_node = ""
    last_transistor: Optional[Component] = None

    if v_out:
        stop_set = ground_nodes | pos_supply_nodes | neg_supply_nodes
        output_chain, output_source_node, last_transistor = _trace_chain(circuit, v_out, stop_set)
        output_chain.reverse()

    # Map components by node
    components_by_node: dict[str, list[Component]] = {}
    for c in circuit.components.values():
        for p in _get_pins(c):
            components_by_node.setdefault(p, []).append(c)

    # Identify tail / active bias transistors
    tail_candidates: list[tuple[Component, str]] = []
    forward_transistors: list[Component] = []

    for q in all_transistors:
        q_pins = q.pins if isinstance(q.pins, dict) else {}
        coll_n = q_pins.get("collector", q_pins.get("drain", ""))
        
        # Check if collector connects to emitter of another transistor
        is_tail = False
        host_id = None
        for other_q in all_transistors:
            if other_q.id == q.id:
                continue
            other_pins = other_q.pins if isinstance(other_q.pins, dict) else {}
            other_emit = other_pins.get("emitter", other_pins.get("source", ""))
            if coll_n == other_emit and coll_n != "":
                is_tail = True
                host_id = other_q.id
                break
        
        if is_tail and host_id:
            tail_candidates.append((q, host_id))
        else:
            forward_transistors.append(q)

    used_components: set[str] = {c.id for c in input_chain} | {c.id for c in output_chain}
    stages: list[StageLayout] = []
    tail_stages: list[StageLayout] = []
    x_cursor = 1.0

    y_vcc = 8.5
    y_gnd = 0.5
    y_vee = 0.5
    y_fwd = 5.5
    y_fb = 2.2

    # Layout forward stages
    for idx, q in enumerate(forward_transistors):
        used_components.add(q.id)
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

        # Detect input and output pins
        if idx == 0:
            if input_target_node == emit_node:
                input_pin = "emitter" if is_bjt else "source"
            else:
                input_pin = "base" if is_bjt else "gate"
        else:
            prev_stage = stages[idx - 1]
            prev_out_node = (
                prev_stage.collector_drain_node
                if prev_stage.output_pin_name in ("collector", "drain")
                else prev_stage.emitter_source_node
            )
            if emit_node == prev_out_node:
                input_pin = "emitter" if is_bjt else "source"
            else:
                input_pin = "base" if is_bjt else "gate"

        # Determine output pin: if collector is tied to positive supply, output must be emitter
        if coll_node in pos_supply_nodes:
            output_pin = "emitter" if is_bjt else "source"
        elif emit_node in ground_nodes or emit_node in neg_supply_nodes:
            output_pin = "collector" if is_bjt else "drain"
        elif idx == len(forward_transistors) - 1 and output_source_node:
            if output_source_node == emit_node:
                output_pin = "emitter" if is_bjt else "source"
            else:
                output_pin = "collector" if is_bjt else "drain"
        else:
            if input_pin in ("emitter", "source"):
                output_pin = "collector" if is_bjt else "drain"
            else:
                output_pin = "collector" if is_bjt else "drain"

        is_cb_cg = input_pin in ("emitter", "source")
        if is_cb_cg:
            in_len = len(input_chain) if idx == 0 and input_chain else 1
            x_bias = x_cursor + 2.0
            x_stage = x_bias + max(4.0, in_len * 2.2 + 1.5)
        else:
            x_bias = x_cursor + 1.8
            x_stage = x_bias + 2.8

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
            y_trans=y_fwd,
        )

        if idx == 0 and input_chain:
            stage.input_chain = input_chain

        if idx == len(forward_transistors) - 1 and output_chain:
            stage.output_chain = output_chain

        # Direct ties to rails
        if coll_node in pos_supply_nodes:
            stage.direct_ties["collector" if is_bjt else "drain"] = coll_node
        if emit_node in ground_nodes:
            stage.direct_ties["emitter" if is_bjt else "source"] = emit_node
        elif emit_node in neg_supply_nodes:
            stage.direct_ties["emitter" if is_bjt else "source"] = emit_node
        if base_node in ground_nodes:
            stage.direct_ties["base" if is_bjt else "gate"] = base_node

        # Base/Gate node components (also check v_in if stage 0 and divider is before input cap)
        candidate_base_nodes = [base_node]
        if idx == 0 and v_in:
            candidate_base_nodes.append(v_in)

        for b_node in candidate_base_nodes:
            for c in components_by_node.get(b_node, []):
                if c.id in used_components:
                    continue
                if c.type in (ComponentType.BJT, ComponentType.MOSFET, ComponentType.JFET, ComponentType.OPAMP):
                    continue
                cpins = _get_pins(c)
                if any(s in pos_supply_nodes for s in cpins):
                    stage.base_gate_pullup.append(c)
                    used_components.add(c.id)
                elif any(g in ground_nodes for g in cpins):
                    if c.type == ComponentType.CAPACITOR:
                        stage.base_gate_bypass.append(c)
                    else:
                        stage.base_gate_pulldown.append(c)
                    used_components.add(c.id)

        # Collector/Drain node components
        for c in components_by_node.get(coll_node, []):
            if c.id in used_components:
                continue
            if c.type in (ComponentType.BJT, ComponentType.MOSFET, ComponentType.JFET, ComponentType.OPAMP):
                continue
            cpins = _get_pins(c)
            if any(s in pos_supply_nodes for s in cpins):
                stage.collector_drain_pullup.append(c)
                used_components.add(c.id)
            elif any(g in ground_nodes for g in cpins):
                stage.collector_drain_pulldown.append(c)
                used_components.add(c.id)
            elif any(v in neg_supply_nodes for v in cpins):
                stage.collector_drain_pulldown.append(c)
                used_components.add(c.id)

        # Emitter/Source node components
        for c in components_by_node.get(emit_node, []):
            if c.id in used_components:
                continue
            if c.type in (ComponentType.BJT, ComponentType.MOSFET, ComponentType.JFET, ComponentType.OPAMP):
                continue
            cpins = _get_pins(c)
            if any(g in ground_nodes for g in cpins):
                if c.type == ComponentType.CAPACITOR:
                    stage.emitter_source_bypass.append([c])
                else:
                    stage.emitter_source_pulldown.append(c)
                used_components.add(c.id)
            elif any(v in neg_supply_nodes for v in cpins):
                stage.emitter_source_pulldown_vee.append(c)
                used_components.add(c.id)
            else:
                # Potential bypass chain: only if intermediate nodes do NOT touch another transistor
                other_pin = cpins[1] if cpins[0] == emit_node else cpins[0]
                if other_pin in all_trans_pins:
                    continue  # Connects to another transistor, not a passive bypass branch!
                
                branch_comps = [c]
                curr_p = other_pin
                is_valid_branch = True
                while curr_p not in ground_nodes and curr_p not in neg_supply_nodes:
                    if curr_p in all_trans_pins:
                        is_valid_branch = False
                        break
                    next_c = [
                        nxt for nxt in components_by_node.get(curr_p, [])
                        if nxt not in branch_comps and nxt.id not in used_components
                        and nxt.type not in (ComponentType.BJT, ComponentType.MOSFET, ComponentType.JFET, ComponentType.OPAMP)
                    ]
                    if not next_c:
                        is_valid_branch = False
                        break
                    branch_comps.append(next_c[0])
                    npins = _get_pins(next_c[0])
                    curr_p = npins[1] if npins[0] == curr_p else npins[0]
                if is_valid_branch and (curr_p in ground_nodes or curr_p in neg_supply_nodes):
                    stage.emitter_source_bypass.append(branch_comps)
                    for bc in branch_comps:
                        used_components.add(bc.id)

        # Output load components at v_out
        if idx == len(forward_transistors) - 1 and v_out:
            for c in components_by_node.get(v_out, []):
                if c.id in used_components:
                    continue
                cpins = _get_pins(c)
                if any(g in ground_nodes for g in cpins):
                    stage.load_components.append(c)
                    used_components.add(c.id)
                elif any(v in neg_supply_nodes for v in cpins):
                    stage.load_components_vee.append(c)
                    used_components.add(c.id)

        stages.append(stage)
        x_cursor = x_stage + 3.8

    # Layout tail bias stages
    for q, host_id in tail_candidates:
        used_components.add(q.id)
        is_bjt = q.type == ComponentType.BJT
        pins = q.pins if isinstance(q.pins, dict) else {}
        base_node = pins.get("base", "")
        coll_node = pins.get("collector", "")
        emit_node = pins.get("emitter", "")

        host_stage = next((s for s in stages if s.transistor.id == host_id), stages[0] if stages else None)
        x_tail = (host_stage.x_stage + 4.2) if host_stage else 7.5

        tail_stage = StageLayout(
            stage_index=len(stages) + len(tail_stages),
            transistor=q,
            is_bjt=is_bjt,
            is_nmos=False,
            is_pnp=False,
            base_gate_node=base_node,
            collector_drain_node=coll_node,
            emitter_source_node=emit_node,
            input_pin_name="base",
            output_pin_name="collector",
            is_tail_bias=True,
            host_transistor_id=host_id,
            x_stage=x_tail,
            x_bias=x_tail - 1.5,
            y_trans=y_fb,
        )

        for c in components_by_node.get(emit_node, []):
            if c.id in used_components:
                continue
            cpins = _get_pins(c)
            if any(g in ground_nodes for g in cpins):
                tail_stage.emitter_source_pulldown.append(c)
                used_components.add(c.id)
            elif any(v in neg_supply_nodes for v in cpins):
                tail_stage.emitter_source_pulldown_vee.append(c)
                used_components.add(c.id)

        for c in components_by_node.get(base_node, []):
            if c.id in used_components:
                continue
            cpins = _get_pins(c)
            if any(g in ground_nodes for g in cpins):
                tail_stage.base_gate_pulldown.append(c)
                used_components.add(c.id)
            elif any(v in neg_supply_nodes for v in cpins):
                tail_stage.base_gate_pulldown.append(c)
                used_components.add(c.id)

        tail_stages.append(tail_stage)

    # Any remaining 2-pin components are bridge / feedback components (e.g. RE2, RBC2, Cext)
    bridge_components: list[Component] = []
    for c in circuit.components.values():
        if c.id not in used_components and c.type not in (
            ComponentType.BJT, ComponentType.MOSFET, ComponentType.JFET, ComponentType.OPAMP
        ):
            bridge_components.append(c)

    total_width = max(x_cursor + 2.5, 12.0)

    return CircuitLayoutPlan(
        circuit_id=circuit.circuit_id,
        is_active_amplifier=True,
        stages=stages,
        tail_stages=tail_stages,
        bridge_components=bridge_components,
        supply_node_id=v_sup,
        negative_supply_node_id=v_neg,
        ground_node_id=gnd,
        pos_supply_nodes=pos_supply_nodes,
        neg_supply_nodes=neg_supply_nodes,
        ground_nodes=ground_nodes,
        input_node_id=v_in,
        output_node_id=v_out,
        width=total_width,
        height=9.0,
        y_vcc=y_vcc,
        y_gnd=y_gnd,
        y_vee=y_vee,
        y_fwd=y_fwd,
        y_fb=y_fb,
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
        width=len(passive_components) * 2.2 + 2.0,
        height=6.0,
    )
