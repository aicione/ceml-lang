"""Schematic Drawing Renderer using SchemDraw.

Consumes a CircuitLayoutPlan and produces publication-quality 2D vector (SVG, PDF)
and raster (PNG) schematic drawings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import schemdraw
import schemdraw.elements as elm

from ceml.models import Circuit, ComponentType
from ceml.schematic.elements import format_component_label, get_schem_element
from ceml.schematic.layout import CircuitLayoutPlan, StageLayout, plan_circuit_layout


def create_schematic_drawing(circuit: Circuit) -> schemdraw.Drawing:
    """Builds and returns a populated SchemDraw Drawing object for a CEML circuit."""
    plan = plan_circuit_layout(circuit)
    d = schemdraw.Drawing(show=False)

    if plan.is_active_amplifier:
        _render_active_amplifier(d, plan)
    else:
        _render_passive_circuit(d, plan)

    return d


def _render_active_amplifier(d: schemdraw.Drawing, plan: CircuitLayoutPlan) -> None:
    """Renders active semiconductor amplifier stages with clean orthogonal routing."""
    for idx, stage in enumerate(plan.stages):
        is_common_base_or_gate = stage.input_pin_name in ("emitter", "source")

        # Adjust stage x coordinates for Common Gate / Base
        if is_common_base_or_gate:
            x_b1 = stage.x_bias - 0.5
            x_b2 = x_b1 + 1.4
            x_q = stage.x_stage
        else:
            x_b1 = stage.x_bias
            x_b2 = stage.x_bias + 1.2
            x_q = stage.x_stage

        # 1. Place active transistor
        trans_el = get_schem_element(stage.transistor)
        anchor_pin = "base" if stage.is_bjt else "gate"
        trans_el.at((x_q, stage.y_mid)).anchor(anchor_pin)
        q_drawn = d.add(trans_el)

        c_pt = q_drawn.collector if stage.is_bjt else q_drawn.drain
        e_pt = q_drawn.emitter if stage.is_bjt else q_drawn.source
        b_pt = q_drawn.base if stage.is_bjt else q_drawn.gate

        # 2. Base / Gate Biasing Network
        has_pd = bool(stage.base_gate_pulldown)
        has_byp = bool(stage.base_gate_bypass)

        if has_pd and has_byp:
            d.add(elm.Line().at((x_b1, stage.y_mid)).to((x_b2, stage.y_mid)))
            d.add(elm.Line().at((x_b2, stage.y_mid)).to(b_pt))

            for pd in stage.base_gate_pulldown:
                el = get_schem_element(pd).at((x_b1, stage.y_mid)).to((x_b1, stage.y_bot + 0.5))
                d.add(el)
                d.add(elm.Ground().at((x_b1, stage.y_bot + 0.5)))

            for bp in stage.base_gate_bypass:
                el = get_schem_element(bp).at((x_b2, stage.y_mid)).to((x_b2, stage.y_bot + 0.5))
                d.add(el)
                d.add(elm.Ground().at((x_b2, stage.y_bot + 0.5)))

            for pu in stage.base_gate_pullup:
                el = get_schem_element(pu).at((x_b1, stage.y_mid)).to((x_b1, stage.y_top + 0.5))
                d.add(el)
                d.add(elm.Vdd().at((x_b1, stage.y_top + 0.5)).label(plan.supply_node_id))
        else:
            d.add(elm.Line().at((x_b1, stage.y_mid)).to(b_pt))

            for pd in stage.base_gate_pulldown:
                el = get_schem_element(pd).at((x_b1, stage.y_mid)).to((x_b1, stage.y_bot + 0.5))
                d.add(el)
                d.add(elm.Ground().at((x_b1, stage.y_bot + 0.5)))

            for bp in stage.base_gate_bypass:
                el = get_schem_element(bp).at((x_b1, stage.y_mid)).to((x_b1, stage.y_bot + 0.5))
                d.add(el)
                d.add(elm.Ground().at((x_b1, stage.y_bot + 0.5)))

            for pu in stage.base_gate_pullup:
                el = get_schem_element(pu).at((x_b1, stage.y_mid)).to((x_b1, stage.y_top + 0.5))
                d.add(el)
                d.add(elm.Vdd().at((x_b1, stage.y_top + 0.5)).label(plan.supply_node_id))

        # 3. Input signal chain (Stage 0)
        if idx == 0 and plan.input_node_id and stage.input_chain:
            num_in = len(stage.input_chain)

            if is_common_base_or_gate:
                # Signal enters Emitter/Source horizontally underneath Gate rail
                y_in = e_pt[1]
                target_x = e_pt[0]
                x_in = x_b2 + 0.8
                dx = (target_x - x_in) / num_in

                d.add(elm.Dot().at((x_in, y_in)).label(plan.input_node_id, loc="left"))
                x_curr = x_in
                for comp in stage.input_chain:
                    x_next = x_curr + dx
                    el = get_schem_element(comp, label_loc="bottom").at((x_curr, y_in)).to((x_next, y_in))
                    d.add(el)
                    x_curr = x_next
            else:
                # Signal enters Base/Gate from far left
                y_in = stage.y_mid
                target_x = x_b1
                span = max(2.5, num_in * 1.8)
                x_in = max(0.0, target_x - span)
                dx = (target_x - x_in) / num_in

                d.add(elm.Dot().at((x_in, y_in)).label(plan.input_node_id, loc="left"))
                x_curr = x_in
                for comp in stage.input_chain:
                    x_next = x_curr + dx
                    el = get_schem_element(comp).at((x_curr, y_in)).to((x_next, y_in))
                    d.add(el)
                    x_curr = x_next

        # 4. Collector / Drain pull-up
        for pu in stage.collector_drain_pullup:
            el = get_schem_element(pu).at(c_pt).to((c_pt[0], stage.y_top + 0.5))
            d.add(el)
            d.add(elm.Vdd().at((c_pt[0], stage.y_top + 0.5)).label(plan.supply_node_id))

        # 5. Emitter / Source pull-down & bypass
        for pd in stage.emitter_source_pulldown:
            el = get_schem_element(pd).at(e_pt).to((e_pt[0], stage.y_bot + 0.5))
            d.add(el)
            d.add(elm.Ground().at((e_pt[0], stage.y_bot + 0.5)))

        for idx_bp, branch in enumerate(stage.emitter_source_bypass):
            x_byp = e_pt[0] + 1.4 * (idx_bp + 1)
            d.add(elm.Line().at(e_pt).to((x_byp, e_pt[1])))
            if len(branch) == 1:
                comp = branch[0]
                el = get_schem_element(comp).at((x_byp, e_pt[1])).to((x_byp, stage.y_bot + 0.5))
                d.add(el)
                d.add(elm.Ground().at((x_byp, stage.y_bot + 0.5)))
            elif len(branch) > 1:
                y_curr = e_pt[1]
                dy = (e_pt[1] - (stage.y_bot + 0.5)) / len(branch)
                for comp in branch:
                    y_next = y_curr - dy
                    el = get_schem_element(comp).at((x_byp, y_curr)).to((x_byp, y_next))
                    d.add(el)
                    y_curr = y_next
                d.add(elm.Ground().at((x_byp, stage.y_bot + 0.5)))

        # 6. Output chain & load (Final stage)
        if stage.output_chain and plan.output_node_id:
            src_pt = c_pt if stage.output_pin_name in ("collector", "drain") else e_pt
            y_out = src_pt[1]

            x_out_start = src_pt[0] + 0.8
            d.add(elm.Line().at(src_pt).to((x_out_start, y_out)))

            x_curr = x_out_start
            for comp in stage.output_chain:
                x_next = x_curr + 1.8
                el = get_schem_element(comp, label_loc="top").at((x_curr, y_out)).to((x_next, y_out))
                d.add(el)
                x_curr = x_next

            # Terminal dot at Vout
            d.add(elm.Dot().at((x_curr, y_out)).label(plan.output_node_id, loc="right"))

            # Load components
            for idx_l, load_c in enumerate(stage.load_components):
                x_load = x_curr + (idx_l * 1.4)
                if idx_l > 0:
                    d.add(elm.Line().at((x_curr, y_out)).to((x_load, y_out)))
                el = get_schem_element(load_c).at((x_load, y_out)).to((x_load, stage.y_bot + 0.5))
                d.add(el)
                d.add(elm.Ground().at((x_load, stage.y_bot + 0.5)))


def _render_passive_circuit(d: schemdraw.Drawing, plan: CircuitLayoutPlan) -> None:
    """Renders single-loop or passive ladder networks."""
    x = 1.0
    y = 3.0

    if plan.passive_chain:
        first = plan.passive_chain[0]
        el = get_schem_element(first).at((x, 0.5)).to((x, y))
        d.add(el)
        d.add(elm.Ground().at((x, 0.5)))

        for comp in plan.passive_chain[1:-1]:
            x_next = x + 2.5
            el = get_schem_element(comp).at((x, y)).to((x_next, y))
            d.add(el)
            x = x_next

        if len(plan.passive_chain) > 1:
            last = plan.passive_chain[-1]
            x_last = x + 2.0
            d.add(elm.Line().at((x, y)).to((x_last, y)))
            el = get_schem_element(last).at((x_last, y)).to((x_last, 0.5))
            d.add(el)
            d.add(elm.Ground().at((x_last, 0.5)))


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
