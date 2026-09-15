"""Tests for CEML Parser."""

import pytest
from ceml.parser import (
    CemlParseError,
    loads,
    parse_engineering_value,
    parse_function_call,
)
from ceml.models import FunctionCall, NodeType, Polarity, Regime, AcBehavior


def test_parse_engineering_value_pure_numbers():
    v1 = parse_engineering_value(12)
    assert v1.numeric == 12.0
    assert not v1.is_symbolic

    v2 = parse_engineering_value(0.7)
    assert v2.numeric == 0.7

    v3 = parse_engineering_value("-5")
    assert v3.numeric == -5.0


def test_parse_engineering_value_standard_suffixes():
    assert parse_engineering_value("10k").numeric == 10_000.0
    assert parse_engineering_value("2m").numeric == pytest.approx(0.002)
    assert parse_engineering_value("12p").numeric == pytest.approx(12e-12)
    assert parse_engineering_value("100u").numeric == pytest.approx(100e-6)
    assert parse_engineering_value("1G").numeric == 1e9


def test_parse_engineering_value_shorthand():
    # Decision #27: 4k7 accepted as shorthand for 4.7k
    v1 = parse_engineering_value("4k7")
    assert v1.numeric == 4700.0
    assert v1.raw == "4k7"

    v2 = parse_engineering_value("1k5")
    assert v2.numeric == 1500.0

    v3 = parse_engineering_value("3k9")
    assert v3.numeric == 3900.0


def test_parse_engineering_value_comma_rejected():
    # Decision #17: comma is rejected as decimal separator
    with pytest.raises(CemlParseError, match="Comma ',' is not accepted"):
        parse_engineering_value("4,7k")

    with pytest.raises(CemlParseError, match="Comma ',' is not accepted"):
        parse_engineering_value("0,7")


def test_parse_engineering_value_symbolic():
    v = parse_engineering_value("2 * R1")
    assert v.is_symbolic
    assert v.numeric is None
    assert v.raw == "2 * R1"


def test_parse_function_call():
    # Bare string
    assert parse_function_call("RC") == "RC"

    # Standard function
    fn1 = parse_function_call("Av(Vout, Vin)")
    assert isinstance(fn1, FunctionCall)
    assert fn1.name == "Av"
    assert fn1.args == ["Vout", "Vin"]
    assert not fn1.has_hf

    # With hf
    fn2 = parse_function_call("Av(Vout, Vin, hf)")
    assert isinstance(fn2, FunctionCall)
    assert fn2.name == "Av"
    assert fn2.args == ["Vout", "Vin"]
    assert fn2.has_hf

    # Commercial
    fn3 = parse_function_call("Commercial(RE, min)")
    assert isinstance(fn3, FunctionCall)
    assert fn3.name == "Commercial"
    assert fn3.args == ["RE", "min"]

    # Expr
    fn4 = parse_function_call("Expr(Vo, Vin1, Vin2, Vin3)")
    assert isinstance(fn4, FunctionCall)
    assert fn4.name == "Expr"
    assert fn4.args == ["Vo", "Vin1", "Vin2", "Vin3"]


def test_loads_simple_circuit():
    yaml_text = """
ceml_version: "0.1"
circuit_id: "test_simple"
description: "Simple test circuit"

nodes:
    - id: GND
      type: ground
    - id: Vin
      type: input
    - id: N1

components:
    - id: R1
      type: resistor
      value: 4k7
      pins: [Vin, N1]

specs:
  find:
    - N1
"""
    circuit = loads(yaml_text)
    assert circuit.circuit_id == "test_simple"
    assert len(circuit.nodes) == 3
    assert circuit.nodes["GND"].type == NodeType.GROUND
    assert circuit.nodes["Vin"].type == NodeType.INPUT
    assert circuit.nodes["N1"].type == NodeType.INTERNAL  # Defaulted

    assert "R1" in circuit.components
    r1 = circuit.components["R1"]
    assert r1.value.numeric == 4700.0
    assert r1.pins == ["Vin", "N1"]
