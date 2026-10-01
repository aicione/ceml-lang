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
        return f"{component.id}\n{component.value.raw}"
    return component.id


def get_schem_element(component: Component, label_loc: Optional[str] = None) -> elm.Element:
    """Creates the appropriate SchemDraw element for a given CEML component."""
    lbl = format_component_label(component)
    comp_type = component.type

    if comp_type == ComponentType.RESISTOR:
        el = elm.Resistor()
        return el.label(lbl, loc=label_loc) if label_loc else el.label(lbl)

    elif comp_type == ComponentType.CAPACITOR:
        el = elm.Capacitor()
        return el.label(lbl, loc=label_loc) if label_loc else el.label(lbl)

    elif comp_type == ComponentType.INDUCTOR:
        el = elm.Inductor()
        return el.label(lbl, loc=label_loc) if label_loc else el.label(lbl)

    elif comp_type == ComponentType.BJT:
        polarity = getattr(component, "polarity", "NPN")
        if polarity == "PNP":
            return elm.BjtPnp().label(component.id, loc="right")
        return elm.BjtNpn().label(component.id, loc="right")

    elif comp_type == ComponentType.MOSFET:
        polarity = getattr(component, "polarity", "NMOS")
        if polarity == "PMOS":
            return elm.PFet().reverse().label(component.id, loc="right")
        return elm.NFet().reverse().label(component.id, loc="right")

    elif comp_type == ComponentType.JFET:
        polarity = getattr(component, "polarity", "N")
        if polarity == "P":
            return elm.PFet().reverse().label(component.id, loc="right")
        return elm.NFet().reverse().label(component.id, loc="right")

    elif comp_type == ComponentType.VOLTAGE_SOURCE:
        if getattr(component, "regime", None) == Regime.AC:
            el = elm.SourceSin()
            return el.label(lbl, loc=label_loc) if label_loc else el.label(lbl)
        el = elm.SourceV()
        return el.label(lbl, loc=label_loc) if label_loc else el.label(lbl)

    elif comp_type == ComponentType.CURRENT_SOURCE:
        if getattr(component, "regime", None) == Regime.AC:
            el = elm.SourceSin()
            return el.label(lbl, loc=label_loc) if label_loc else el.label(lbl)
        el = elm.SourceI()
        return el.label(lbl, loc=label_loc) if label_loc else el.label(lbl)

    elif comp_type == ComponentType.DIODE:
        el = elm.Diode()
        return el.label(lbl, loc=label_loc) if label_loc else el.label(lbl)

    elif comp_type == ComponentType.OPAMP:
        return elm.Opamp().label(component.id)

    # Fallback to generic box / resistor
    return elm.Resistor().label(lbl)
