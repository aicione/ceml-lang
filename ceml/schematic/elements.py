"""Mapping from CEML Component AST models to SchemDraw elements.

Provides standardized graphical representations, terminal anchors, and component labels.
"""

from __future__ import annotations

from typing import Optional, Union

import schemdraw.elements as elm
from ceml.models import Component, ComponentType, Regime


def format_component_label(component: Component) -> str:
    """Formats human-readable display label for a component (ID and optional value)."""
    if component.value and component.value.raw:
        if component.value.raw == component.id:
            return component.id
        return f"{component.id}\n{component.value.raw}"
    return component.id


def get_schem_element(
    component: Component,
    direction: Optional[str] = None,
    label_loc: Optional[str] = None,
) -> elm.Element:
    """Creates the appropriate SchemDraw element for a given CEML component."""
    lbl = format_component_label(component)
    comp_type = component.type

    def _apply_dir(elem: elm.Element) -> elm.Element:
        if direction == "down":
            return elem.down()
        elif direction == "up":
            return elem.up()
        elif direction == "left":
            return elem.left()
        elif direction == "right":
            return elem.right()
        return elem

    if comp_type == ComponentType.RESISTOR:
        el = _apply_dir(elm.Resistor())
        return el.label(lbl, loc=label_loc) if label_loc else el.label(lbl)

    elif comp_type == ComponentType.CAPACITOR:
        el = _apply_dir(elm.Capacitor())
        return el.label(lbl, loc=label_loc) if label_loc else el.label(lbl)

    elif comp_type == ComponentType.INDUCTOR:
        el = _apply_dir(elm.Inductor())
        return el.label(lbl, loc=label_loc) if label_loc else el.label(lbl)

    elif comp_type == ComponentType.BJT:
        polarity = getattr(component, "polarity", "NPN")
        if polarity == "PNP":
            return elm.BjtPnp().right()
        return elm.BjtNpn().right()

    elif comp_type == ComponentType.MOSFET:
        polarity = getattr(component, "polarity", "NMOS")
        if polarity == "PMOS":
            return elm.PFet().reverse().right()
        return elm.NFet().reverse().right()

    elif comp_type == ComponentType.JFET:
        polarity = getattr(component, "polarity", "N")
        if polarity == "P":
            return elm.PFet().reverse().right()
        return elm.NFet().reverse().right()

    elif comp_type == ComponentType.VOLTAGE_SOURCE:
        if getattr(component, "regime", None) == Regime.AC:
            el = _apply_dir(elm.SourceSin())
            return el.label(lbl, loc=label_loc) if label_loc else el.label(lbl)
        el = _apply_dir(elm.SourceV())
        return el.label(lbl, loc=label_loc) if label_loc else el.label(lbl)

    elif comp_type == ComponentType.CURRENT_SOURCE:
        if getattr(component, "regime", None) == Regime.AC:
            el = _apply_dir(elm.SourceSin())
            return el.label(lbl, loc=label_loc) if label_loc else el.label(lbl)
        el = _apply_dir(elm.SourceI())
        return el.label(lbl, loc=label_loc) if label_loc else el.label(lbl)

    elif comp_type == ComponentType.DIODE:
        el = _apply_dir(elm.Diode())
        return el.label(lbl, loc=label_loc) if label_loc else el.label(lbl)

    elif comp_type == ComponentType.OPAMP:
        return elm.Opamp().right().label(component.id)

    # Fallback to generic box / resistor
    el = _apply_dir(elm.Resistor())
    return el.label(lbl, loc=label_loc) if label_loc else el.label(lbl)
