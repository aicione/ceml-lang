"""Schematic Drawing Renderer using SchemDraw.

Consumes a CircuitLayoutPlan and produces publication-quality 2D vector (SVG, PDF)
and raster (PNG) schematic drawings using a Two-Phase Placement & Routing architecture.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Optional, Union

import schemdraw
import schemdraw.elements as elm

from ceml.models import Circuit, ComponentType
from ceml.schematic.elements import format_component_label, get_schem_element
from ceml.schematic.layout import CircuitLayoutPlan, StageLayout, plan_circuit_layout


def create_schematic_drawing(circuit: Circuit) -> schemdraw.Drawing:
    """Builds and returns a populated SchemDraw Drawing object for a CEML circuit."""
    plan = plan_circuit_layout(circuit)
    d = schemdraw.Drawing(show=False)
    d.config(fontsize=10)

    if plan.is_opamp_circuit:
        _render_opamp_circuit(d, circuit, plan)
    elif plan.is_active_amplifier:
        _render_active_amplifier(d, circuit, plan)
    else:
        _render_passive_circuit(d, plan)

    return d


def _render_active_amplifier(d: schemdraw.Drawing, circuit: Circuit, plan: CircuitLayoutPlan) -> None:
    """Renders active semiconductor amplifier stages with clean orthogonal routing."""
    y_vcc = plan.y_vcc
    y_gnd = plan.y_gnd
    y_vee = plan.y_vee
    y_fwd = plan.y_fwd
    y_fb = plan.y_fb
    pos_rail = plan.supply_node_id or "VCC"
    neg_rail = plan.negative_supply_node_id or "VEE"

    pin_anchors: dict[str, list[tuple[str, str, Any]]] = defaultdict(list)

    # ==================== PHASE 1: COMPONENT PLACEMENT ====================

    # 1. Input signal chain (Stage 0)
    if plan.input_node_id and plan.stages and plan.stages[0].input_chain:
        stage0 = plan.stages[0]
        x_in = 0.5
        y_in = y_fwd
        target_x = stage0.x_bias

        d.add(elm.Dot().at((x_in, y_in)).label(plan.input_node_id, loc="left"))
        curr_x = x_in
        num_in = len(stage0.input_chain)
        dx = (target_x - x_in) / num_in
        for c in stage0.input_chain:
            next_x = curr_x + dx
            d.add(get_schem_element(c, direction="right", label_loc="top").at((curr_x, y_in)).to((next_x, y_in)))
            curr_x = next_x
        d.add(elm.Dot().at((target_x, y_in)))

    # 2. Forward Stages Placement
    for idx, stage in enumerate(plan.stages):
        is_cb_cg = stage.input_pin_name in ("emitter", "source")
        q_elem = get_schem_element(stage.transistor)
        anchor_pin = "base" if stage.is_bjt else "gate"
        q_drawn = d.add(q_elem.at((stage.x_stage, stage.y_trans)).anchor(anchor_pin))

        # Transistor label placed safely to avoid collision with leads
        d.add(elm.Label().at(q_drawn.center).label(stage.transistor.id, loc="left", ofst=(-0.35, 0.35)))

        c_pt = q_drawn.collector if stage.is_bjt else q_drawn.drain
        e_pt = q_drawn.emitter if stage.is_bjt else q_drawn.source
        b_pt = q_drawn.base if stage.is_bjt else q_drawn.gate

        pin_anchors[stage.collector_drain_node].append((stage.transistor.id, "collector", c_pt))
        pin_anchors[stage.emitter_source_node].append((stage.transistor.id, "emitter", e_pt))
        pin_anchors[stage.base_gate_node].append((stage.transistor.id, "base", b_pt))

        # Direct ties to power or ground rails
        for pin_name, rail_id in stage.direct_ties.items():
            if pin_name in ("collector", "drain"):
                d.add(elm.Line().up().at(c_pt).to((c_pt[0], y_vcc)))
                d.add(elm.Vdd().at((c_pt[0], y_vcc)).label(rail_id))
            elif pin_name in ("emitter", "source"):
                if rail_id in plan.neg_supply_nodes:
                    d.add(elm.Line().down().at(e_pt).to((e_pt[0], y_vee)))
                    d.add(elm.Vdd().at((e_pt[0], y_vee)).reverse().label(rail_id, loc="bot"))
                else:
                    d.add(elm.Line().down().at(e_pt).to((e_pt[0], y_gnd)))
                    d.add(elm.Ground().at((e_pt[0], y_gnd)))
            elif pin_name in ("base", "gate"):
                d.add(elm.Line().down().at(b_pt).to((b_pt[0], y_gnd)))
                d.add(elm.Ground().at((b_pt[0], y_gnd)))

        # Base / Gate network
        if not is_cb_cg:
            has_base_network = stage.base_gate_pullup or stage.base_gate_pulldown or stage.base_gate_bypass
            if idx == 0 or has_base_network:
                d.add(elm.Line().right().at((stage.x_bias, b_pt[1])).to(b_pt))
            if has_base_network:
                d.add(elm.Dot().at((stage.x_bias, b_pt[1])))
                for pu in stage.base_gate_pullup:
                    d.add(get_schem_element(pu, direction="up", label_loc="top").at((stage.x_bias, b_pt[1])).to((stage.x_bias, y_vcc)))
                    d.add(elm.Vdd().at((stage.x_bias, y_vcc)).label(pos_rail))
                for pd in stage.base_gate_pulldown:
                    d.add(get_schem_element(pd, direction="down", label_loc="top").at((stage.x_bias, b_pt[1])).to((stage.x_bias, y_gnd)))
                    d.add(elm.Ground().at((stage.x_bias, y_gnd)))
                for bp in stage.base_gate_bypass:
                    d.add(get_schem_element(bp, direction="down", label_loc="top").at((stage.x_bias, b_pt[1])).to((stage.x_bias, y_gnd)))
                    d.add(elm.Ground().at((stage.x_bias, y_gnd)))
        else:
            # Common Base / Common Gate: base is bypassed / grounded to the left
            d.add(elm.Line().left().at(b_pt).to((stage.x_bias, b_pt[1])))
            d.add(elm.Dot().at((stage.x_bias, b_pt[1])))
            pin_anchors[stage.base_gate_node].append((stage.transistor.id, "base_tap", (stage.x_bias, b_pt[1])))
            for bp in stage.base_gate_bypass:
                d.add(get_schem_element(bp, direction="down", label_loc="top").at((stage.x_bias, b_pt[1])).to((stage.x_bias, y_gnd)))
                d.add(elm.Ground().at((stage.x_bias, y_gnd)))
            for pd in stage.base_gate_pulldown:
                d.add(get_schem_element(pd, direction="down", label_loc="top").at((stage.x_bias, b_pt[1])).to((stage.x_bias, y_gnd)))
                d.add(elm.Ground().at((stage.x_bias, y_gnd)))

        # Collector / Drain pullups
        for pu in stage.collector_drain_pullup:
            d.add(elm.Dot().at(c_pt))
            d.add(get_schem_element(pu, direction="up", label_loc="bot").at(c_pt).to((c_pt[0], y_vcc)))
            d.add(elm.Vdd().at((c_pt[0], y_vcc)).label(pos_rail))

        # Collector / Drain pulldowns (e.g. Q2 collector RC2 in cascade)
        if stage.collector_drain_pulldown:
            x_cd = stage.x_stage + 1.8
            d.add(elm.Line().right().at(c_pt).to((x_cd, c_pt[1])))
            d.add(elm.Dot().at((x_cd, c_pt[1])))
            for pd in stage.collector_drain_pulldown:
                d.add(get_schem_element(pd, direction="down", label_loc="bot").at((x_cd, c_pt[1])).to((x_cd, y_gnd)))
                d.add(elm.Ground().at((x_cd, y_gnd)))
            pin_anchors[stage.collector_drain_node].append((stage.transistor.id, "collector_tap", (x_cd, c_pt[1])))

        # Emitter / Source pulldowns to GND
        if stage.emitter_source_pulldown:
            is_cascade_driver = (len(plan.stages) > 1 and stage.stage_index == 0 and stage.emitter_source_node == plan.stages[1].emitter_source_node)
            x_e_tap = (stage.x_stage + 1.8) if is_cascade_driver else e_pt[0]
            if x_e_tap != e_pt[0]:
                d.add(elm.Line().right().at(e_pt).to((x_e_tap, e_pt[1])))
            d.add(elm.Dot().at((x_e_tap, e_pt[1])))
            for pd in stage.emitter_source_pulldown:
                d.add(get_schem_element(pd, direction="down", label_loc="top").at((x_e_tap, e_pt[1])).to((x_e_tap, y_gnd)))
                d.add(elm.Ground().at((x_e_tap, y_gnd)))
            pin_anchors[stage.emitter_source_node].append((stage.transistor.id, "emitter_tap", (x_e_tap, e_pt[1])))

        # Emitter / Source pulldowns to VEE (resistors, current sources)
        if stage.emitter_source_pulldown_vee:
            comp0 = stage.emitter_source_pulldown_vee[0]
            d.add(elm.Dot().at(e_pt))
            d.add(get_schem_element(comp0, direction="down", label_loc="top").at(e_pt).to((e_pt[0], y_vee)))
            d.add(elm.Vdd().at((e_pt[0], y_vee)).reverse().label(neg_rail, loc="bot"))
            for idx_v, comp in enumerate(stage.emitter_source_pulldown_vee[1:]):
                x_v = stage.x_stage + 1.8 + idx_v * 1.5
                d.add(elm.Line().right().at(e_pt).to((x_v, e_pt[1])))
                d.add(elm.Dot().at((x_v, e_pt[1])))
                d.add(get_schem_element(comp, direction="down", label_loc="bot").at((x_v, e_pt[1])).to((x_v, y_vee)))
                d.add(elm.Vdd().at((x_v, y_vee)).reverse().label(neg_rail, loc="bot"))
                pin_anchors[stage.emitter_source_node].append((stage.transistor.id, "emitter_vee_tap", (x_v, e_pt[1])))

        # Emitter / Source bypass branches
        for idx_bp, branch in enumerate(stage.emitter_source_bypass):
            x_byp = e_pt[0] + 1.4 * (idx_bp + 1)
            d.add(elm.Line().right().at(e_pt).to((x_byp, e_pt[1])))
            d.add(elm.Dot().at((x_byp, e_pt[1])))
            if len(branch) == 1:
                d.add(get_schem_element(branch[0], direction="down", label_loc="bot").at((x_byp, e_pt[1])).to((x_byp, y_gnd)))
                d.add(elm.Ground().at((x_byp, y_gnd)))
            else:
                dy = (e_pt[1] - y_gnd) / len(branch)
                y_curr = e_pt[1]
                for b_comp in branch:
                    y_next = y_curr - dy
                    d.add(get_schem_element(b_comp, direction="down", label_loc="bot").at((x_byp, y_curr)).to((x_byp, y_next)))
                    y_curr = y_next
                d.add(elm.Ground().at((x_byp, y_gnd)))

        # Output chain & loads (Final Stage)
        if stage.output_chain and plan.output_node_id:
            src_anchors = pin_anchors[stage.collector_drain_node] if stage.output_pin_name in ("collector", "drain") else pin_anchors[stage.emitter_source_node]
            src_pt = src_anchors[-1][2] if src_anchors else (c_pt if stage.output_pin_name in ("collector", "drain") else e_pt)

            bypass_extra = len(stage.emitter_source_bypass) * 1.4
            x_out = src_pt[0] + 2.5 + bypass_extra
            y_out = src_pt[1]
            d.add(get_schem_element(stage.output_chain[0], direction="right", label_loc="top").at(src_pt).to((x_out, y_out)))
            d.add(elm.Dot().at((x_out, y_out)).label(plan.output_node_id, loc="right", ofst=0.15))
            pin_anchors[plan.output_node_id].append(("output", "Vout", (x_out, y_out)))

            # Loads to GND
            for idx_l, load_c in enumerate(stage.load_components):
                x_l = x_out + idx_l * 1.5
                if idx_l > 0:
                    d.add(elm.Line().right().at((x_out, y_out)).to((x_l, y_out)))
                d.add(get_schem_element(load_c, direction="down", label_loc="bot" if idx_l > 0 else "top").at((x_l, y_out)).to((x_l, y_gnd)))
                d.add(elm.Ground().at((x_l, y_gnd)))

            # Loads to VEE
            for idx_l, load_c in enumerate(stage.load_components_vee):
                x_l = x_out + idx_l * 1.5
                d.add(get_schem_element(load_c, direction="down", label_loc="bot").at((x_l, y_out)).to((x_l, y_vee)))
                d.add(elm.Vdd().at((x_l, y_vee)).reverse().label(neg_rail, loc="bot"))

    # 3. Tail Stages Placement (Active Emitter / Source Biasing)
    for tail_stage in plan.tail_stages:
        t_el = get_schem_element(tail_stage.transistor).at((tail_stage.x_stage, tail_stage.y_trans)).anchor("base")
        t_drawn = d.add(t_el)
        d.add(elm.Label().at(t_drawn.center).label(tail_stage.transistor.id, loc="left", ofst=(-0.35, 0.35)))

        # Emitter pulldown to GND
        if tail_stage.emitter_source_pulldown:
            d.add(get_schem_element(tail_stage.emitter_source_pulldown[0], direction="down", label_loc="bot").at(t_drawn.emitter).to((t_drawn.emitter[0], y_gnd)))
            d.add(elm.Ground().at((t_drawn.emitter[0], y_gnd)))

        # Base pulldown to GND
        x_rb = tail_stage.x_bias
        d.add(elm.Line().left().at(t_drawn.base).to((x_rb, t_drawn.base[1])))
        d.add(elm.Dot().at((x_rb, t_drawn.base[1])))
        if tail_stage.base_gate_pulldown:
            d.add(get_schem_element(tail_stage.base_gate_pulldown[0], direction="down", label_loc="top").at((x_rb, t_drawn.base[1])).to((x_rb, y_gnd)))
            d.add(elm.Ground().at((x_rb, y_gnd)))
        pin_anchors[tail_stage.base_gate_node].append((tail_stage.transistor.id, "base_tap", (x_rb, t_drawn.base[1])))

        # Collector connects to host stage emitter
        host_anchors = [pt for cid, role, pt in pin_anchors[tail_stage.collector_drain_node] if cid == tail_stage.host_transistor_id and role == "emitter"]
        if host_anchors:
            host_e_pt = host_anchors[0]
            d.add(elm.Line().up().at(t_drawn.collector).to((t_drawn.collector[0], 4.0)))
            d.add(elm.Line().left().at((t_drawn.collector[0], 4.0)).to((host_e_pt[0], 4.0)))
            d.add(elm.Line().up().at((host_e_pt[0], 4.0)).to(host_e_pt))
            d.add(elm.Dot().at(host_e_pt))

    # 4. Bridge / Feedback Components Placement
    for comp in plan.bridge_components:
        pins = comp.pins if isinstance(comp.pins, list) else list(comp.pins.values())
        if comp.id == "RE2" and len(pins) == 2:
            # Feedback from Stage 1 emitter to Tail base
            p_e_matches = [pt for cid, role, pt in pin_anchors[pins[0]] if role == "emitter"]
            p_b_matches = [pt for cid, role, pt in pin_anchors[pins[1]] if role == "base_tap"]
            if p_e_matches and p_b_matches:
                p_e = p_e_matches[0]
                p_b = p_b_matches[0]
                d.add(elm.Line().down().at(p_e).to((p_e[0], y_fb)))
                d.add(get_schem_element(comp, direction="left", label_loc="top").at((p_e[0], y_fb)).to(p_b))
        elif comp.id == "RBC2" and len(pins) == 2:
            # Collector to Base feedback (common base)
            p_coll_matches = [pt for cid, role, pt in pin_anchors[pins[0]] if role == "collector_tap"]
            p_base_matches = [pt for cid, role, pt in pin_anchors[pins[1]] if role == "base_tap"]
            if p_coll_matches and p_base_matches:
                p_coll = p_coll_matches[0]
                p_base = p_base_matches[0]
                y_br = 2.2
                d.add(elm.Dot().at((p_base[0], y_br)))
                d.add(elm.Dot().at((p_coll[0], y_br)))
                d.add(elm.Line().down().at(p_base).to((p_base[0], y_br)))
                d.add(get_schem_element(comp, direction="right", label_loc="top").at((p_base[0], y_br)).to((p_coll[0], y_br)))
                d.add(elm.Line().up().at((p_coll[0], y_br)).to(p_coll))
        elif comp.id == "Cext" and len(pins) == 2:
            # Gate to Source compensation cap
            p_g_matches = [pt for cid, role, pt in pin_anchors[pins[0]] if role == "base"]
            p_s_matches = [pt for cid, role, pt in pin_anchors[pins[1]] if role == "emitter"]
            if p_g_matches and p_s_matches:
                p_g = p_g_matches[0]
                p_s = p_s_matches[0]
                y_br = 7.0
                x_g = plan.stages[0].x_stage - 1.2
                x_s = p_s[0] + 0.8
                d.add(elm.Dot().at((x_g, p_g[1])))
                d.add(elm.Line().up().at((x_g, p_g[1])).to((x_g, y_br)))
                d.add(get_schem_element(comp, direction="right", label_loc="top").at((x_g, y_br)).to((x_s, y_br)))
                d.add(elm.Line().down().at((x_s, y_br)).to((x_s, p_s[1])))
                d.add(elm.Line().right().at(p_s).to((x_s, p_s[1])))
                d.add(elm.Dot().at((x_s, p_s[1])))

    # ==================== PHASE 2: NETLIST ROUTING ====================
    if len(plan.stages) > 1:
        s0 = plan.stages[0]
        s1 = plan.stages[1]
        # CE -> CE (e.g. T1 collector to T2 base in three_npn)
        if s0.collector_drain_node == s1.base_gate_node:
            c0_matches = [pt for cid, role, pt in pin_anchors[s0.collector_drain_node] if cid == s0.transistor.id and role == "collector"]
            b1_matches = [pt for cid, role, pt in pin_anchors[s1.base_gate_node] if cid == s1.transistor.id and role == "base"]
            if c0_matches and b1_matches:
                c0 = c0_matches[0]
                b1 = b1_matches[0]
                d.add(elm.Dot().at(c0))
                d.add(elm.Line().right().at(c0).to((b1[0] - 0.5, c0[1])))
                d.add(elm.Line().down().at((b1[0] - 0.5, c0[1])).to((b1[0] - 0.5, b1[1])))
                d.add(elm.Line().right().at((b1[0] - 0.5, b1[1])).to(b1))

        # CC -> CB (e.g. Q1 emitter to Q2 emitter in cascade)
        if s0.emitter_source_node == s1.emitter_source_node:
            e_tap_matches = [pt for cid, role, pt in pin_anchors[s0.emitter_source_node] if cid == s0.transistor.id and role == "emitter_tap"]
            e_q2_matches = [pt for cid, role, pt in pin_anchors[s1.emitter_source_node] if cid == s1.transistor.id and role == "emitter"]
            if e_tap_matches and e_q2_matches:
                e_tap = e_tap_matches[0]
                e_q2 = e_q2_matches[0]
                x_turn = e_q2[0] + 0.8
                d.add(elm.Dot().at(e_tap))
                if s1.is_pnp:
                    y_top_route = 6.8
                    d.add(elm.Line().up().at(e_tap).to((e_tap[0], y_top_route)))
                    d.add(elm.Line().right().at((e_tap[0], y_top_route)).to((x_turn, y_top_route)))
                    d.add(elm.Line().down().at((x_turn, y_top_route)).to((x_turn, e_q2[1])))
                    d.add(elm.Line().left().at((x_turn, e_q2[1])).to(e_q2))
                else:
                    d.add(elm.Line().right().at(e_tap).to((x_turn, e_tap[1])))
                    d.add(elm.Line().up().at((x_turn, e_tap[1])).to((x_turn, e_q2[1])))
                    d.add(elm.Line().left().at((x_turn, e_q2[1])).to(e_q2))


def _render_passive_circuit(d: schemdraw.Drawing, plan: CircuitLayoutPlan) -> None:
    """Renders single-loop or passive ladder networks."""
    x = 1.0
    y = 3.0

    if plan.passive_chain:
        first = plan.passive_chain[0]
        el = get_schem_element(first, direction="up").at((x, 0.5)).to((x, y))
        d.add(el)
        d.add(elm.Ground().at((x, 0.5)))

        for comp in plan.passive_chain[1:-1]:
            x_next = x + 2.5
            el = get_schem_element(comp, direction="right", label_loc="top").at((x, y)).to((x_next, y))
            d.add(el)
            x = x_next

        if len(plan.passive_chain) > 1:
            last = plan.passive_chain[-1]
            x_last = x + 2.0
            d.add(elm.Line().right().at((x, y)).to((x_last, y)))
            el = get_schem_element(last, direction="down", label_loc="bot").at((x_last, y)).to((x_last, 0.5))
            d.add(el)
            d.add(elm.Ground().at((x_last, 0.5)))


def _render_opamp_circuit(d: schemdraw.Drawing, circuit: Circuit, plan: CircuitLayoutPlan) -> None:
    """Renders operational amplifier circuits (single op-amp or multi-opamp topologies)."""
    opamps = plan.opamps
    comps = circuit.components

    # 1. Opamp 1 (top-left) at (6.5, 8.5)
    op1_comp = comps.get("opamp1", opamps[0])
    op1 = d.add(elm.Opamp().right().at((6.5, 8.5)).label(op1_comp.id, loc="center"))

    # in1 (-) tap at (4.8, in1[1])
    d.add(elm.Line().left().at(op1.in1).to((4.8, op1.in1[1])))
    d.add(elm.Dot().at((4.8, op1.in1[1])))

    # Feedback R3: from (4.8, in1[1]) up to 10.5, over to out, down to out
    r3 = comps.get("R3")
    if r3:
        d.add(elm.Line().up().at((4.8, op1.in1[1])).to((4.8, 10.5)))
        d.add(get_schem_element(r3, direction="right", label_loc="top").at((4.8, 10.5)).to((op1.out[0], 10.5)))
        d.add(elm.Line().down().at((op1.out[0], 10.5)).to(op1.out))

    # R2 to GND: left from 4.8 to 2.5, then down to GND at x = 2.5
    r2 = comps.get("R2")
    if r2:
        d.add(get_schem_element(r2, direction="left", label_loc="top").at((4.8, op1.in1[1])).to((2.5, op1.in1[1])))
        d.add(elm.Line().down().at((2.5, op1.in1[1])).to((2.5, 6.8)))
        d.add(elm.Ground().at((2.5, 6.8)))

    # Vin1 -> R1: starts at x = 3.2, y = op1.in2[1], straight into in2 (+) at (6.5, in2[1])
    r1 = comps.get("R1")
    if r1:
        d.add(elm.Dot().at((3.2, op1.in2[1])).label("Vin1", loc="left"))
        d.add(get_schem_element(r1, direction="right", label_loc="top").at((3.2, op1.in2[1])).to(op1.in2))

    if len(opamps) >= 3:
        # 2. Opamp 3 (bottom-left) at (6.5, 2.5)
        op3_comp = comps.get("opamp3", opamps[2])
        op3 = d.add(elm.Opamp().right().at((6.5, 2.5)).label(op3_comp.id, loc="center"))

        # Vin2 -> R9 -> op3.in1 (in-)
        r9 = comps.get("R9")
        if r9:
            d.add(elm.Dot().at((1.0, op3.in1[1])).label("Vin2", loc="left"))
            d.add(get_schem_element(r9, direction="right", label_loc="top").at((1.0, op3.in1[1])).to(op3.in1))

        # Feedback R8: op3.in1 -> op3.out
        r8 = comps.get("R8")
        if r8:
            d.add(elm.Line().left().at(op3.in1).to((op3.in1[0] - 1.2, op3.in1[1])))
            d.add(elm.Line().up().at((op3.in1[0] - 1.2, op3.in1[1])).to((op3.in1[0] - 1.2, op3.in1[1] + 1.6)))
            d.add(get_schem_element(r8, direction="right", label_loc="top").at((op3.in1[0] - 1.2, op3.in1[1] + 1.6)).to((op3.out[0], op3.in1[1] + 1.6)))
            d.add(elm.Line().down().at((op3.out[0], op3.in1[1] + 1.6)).to(op3.out))

        # Vin3 -> R11 -> N8 -> op3.in2 (+), and R10 to GND
        r11 = comps.get("R11")
        r10 = comps.get("R10")
        if r11 and r10:
            x_n8 = op3.in2[0] - 1.2
            d.add(elm.Dot().at((1.0, op3.in2[1])).label("Vin3", loc="left"))
            d.add(get_schem_element(r11, direction="right", label_loc="top").at((1.0, op3.in2[1])).to((x_n8, op3.in2[1])))
            d.add(elm.Dot().at((x_n8, op3.in2[1])))
            d.add(elm.Line().right().at((x_n8, op3.in2[1])).to(op3.in2))
            d.add(get_schem_element(r10, direction="down", label_loc="top").at((x_n8, op3.in2[1])).to((x_n8, op3.in2[1] - 1.8)))
            d.add(elm.Ground().at((x_n8, op3.in2[1] - 1.8)))

        # 3. Opamp 2 (right summing stage) at (13.5, 5.5)
        op2_comp = comps.get("opamp2", opamps[1])
        op2 = d.add(elm.Opamp().right().at((13.5, 5.5)).label(op2_comp.id, loc="center"))

        # R4: op1.out -> op2.in1
        r4 = comps.get("R4")
        x_sum = op2.in1[0] - 1.8
        if r4:
            d.add(get_schem_element(r4, direction="right", label_loc="top").at(op1.out).to((x_sum, op1.out[1])))
            d.add(elm.Line().down().at((x_sum, op1.out[1])).to((x_sum, op2.in1[1])))
            d.add(elm.Line().right().at((x_sum, op2.in1[1])).to(op2.in1))
            d.add(elm.Dot().at((x_sum, op2.in1[1])))

        # R7: op3.out -> op2.in1
        r7 = comps.get("R7")
        if r7:
            d.add(get_schem_element(r7, direction="right", label_loc="top").at(op3.out).to((x_sum, op3.out[1])))
            d.add(elm.Line().up().at((x_sum, op3.out[1])).to((x_sum, op2.in1[1])))

        # R6: op2.in2 -> GND
        r6 = comps.get("R6")
        if r6:
            d.add(get_schem_element(r6, direction="down", label_loc="top").at(op2.in2).to((op2.in2[0], op2.in2[1] - 1.8)))
            d.add(elm.Ground().at((op2.in2[0], op2.in2[1] - 1.8)))

        # Feedback R5: op2.in1 -> Vo
        r5 = comps.get("R5")
        if r5:
            d.add(elm.Line().up().at((x_sum, op2.in1[1])).to((x_sum, op2.in1[1] + 1.8)))
            d.add(get_schem_element(r5, direction="right", label_loc="top").at((x_sum, op2.in1[1] + 1.8)).to((op2.out[0], op2.in1[1] + 1.8)))
            d.add(elm.Line().down().at((op2.out[0], op2.in1[1] + 1.8)).to(op2.out))

        # Output terminal Vo
        out_node = plan.output_node_id or "Vo"
        d.add(elm.Line().right().at(op2.out).to((op2.out[0] + 1.5, op2.out[1])))
        d.add(elm.Dot().at((op2.out[0] + 1.5, op2.out[1])).label(out_node, loc="right", ofst=0.15))


def render_circuit(
    circuit: Circuit,
    output_path: Union[str, Path],
    format: Optional[str] = None,
) -> Path:
    """Renders a CEML Circuit AST to an image file (PNG, SVG, or PDF).

    Args:
        circuit: Validated CEML Circuit object.
        output_path: Target image file path.
        format: Optional explicit image format override ('png', 'svg', 'pdf').

    Returns:
        Path to the generated image file.
    """
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    drawing = create_schematic_drawing(circuit)
    drawing.save(str(out_file))

    return out_file
