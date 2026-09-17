"""Tests for CEML Validator."""

import pytest
from ceml.parser import loads
from ceml.validator import validate, CemlValidationError


def test_validator_detects_duplicate_node_ids():
    yaml_text = """
ceml_version: "0.1"
circuit_id: "dup_nodes"
nodes:
    - id: GND
      type: ground
    - id: N1
    - id: N1
components: []
"""
    circuit = loads(yaml_text)
    res = validate(circuit)
    assert not res.is_valid
    assert any(e.code == "ERR_DUPLICATE_NODE_ID" for e in res.errors)


def test_validator_detects_duplicate_component_ids():
    yaml_text = """
ceml_version: "0.1"
circuit_id: "dup_comps"
nodes:
    - id: GND
      type: ground
components:
    - id: R1
      type: resistor
      value: 1k
      pins: [GND, GND]
    - id: R1
      type: resistor
      value: 2k
      pins: [GND, GND]
"""
    circuit = loads(yaml_text)
    res = validate(circuit)
    assert not res.is_valid
    assert any(e.code == "ERR_DUPLICATE_COMPONENT_ID" for e in res.errors)


def test_validator_requires_ground():
    yaml_text = """
ceml_version: "0.1"
circuit_id: "no_ground"
nodes:
    - id: N1
      type: input
    - id: N2
      type: output
components:
    - id: R1
      type: resistor
      value: 1k
      pins: [N1, N2]
"""
    circuit = loads(yaml_text)
    res = validate(circuit)
    assert not res.is_valid
    assert any(e.code == "ERR_NO_GROUND" for e in res.errors)


def test_validator_undeclared_node():
    yaml_text = """
ceml_version: "0.1"
circuit_id: "undeclared_node"
nodes:
    - id: GND
      type: ground
components:
    - id: R1
      type: resistor
      value: 1k
      pins: [GND, N_MISSING]
"""
    circuit = loads(yaml_text)
    res = validate(circuit)
    assert not res.is_valid
    assert any(e.code == "ERR_UNDECLARED_NODE" for e in res.errors)


def test_validator_polarized_resistor_fatal():
    yaml_text = """
ceml_version: "0.1"
circuit_id: "bad_resistor"
nodes:
    - id: GND
      type: ground
    - id: N1
components:
    - id: R1
      type: resistor
      value: 1k
      polarized: true
      pins: {p: N1, n: GND}
"""
    circuit = loads(yaml_text)
    res = validate(circuit)
    assert not res.is_valid
    assert any(e.code == "ERR_INVALID_POLARIZATION" for e in res.errors)


def test_validator_source_regime_required():
    yaml_text = """
ceml_version: "0.1"
circuit_id: "bad_source"
nodes:
    - id: GND
      type: ground
    - id: N1
components:
    - id: V1
      type: voltage_source
      value: 10
      pins: {p: N1, n: GND}
"""
    circuit = loads(yaml_text)
    res = validate(circuit)
    assert not res.is_valid
    assert any(e.code == "ERR_INVALID_SOURCE_REGIME" for e in res.errors)


def test_validator_dc_source_cannot_have_rms_or_phase():
    yaml_text = """
ceml_version: "0.1"
circuit_id: "dc_source_rms"
nodes:
    - id: GND
      type: ground
    - id: N1
components:
    - id: V1
      type: voltage_source
      regime: DC
      value: 10
      rms: true
      pins: {p: N1, n: GND}
"""
    circuit = loads(yaml_text)
    res = validate(circuit)
    assert not res.is_valid
    assert any(e.code == "ERR_DC_SOURCE_AC_FIELDS" for e in res.errors)


def test_validator_expr_cannot_reference_ground_or_supply():
    yaml_text = """
ceml_version: "0.1"
circuit_id: "expr_ground"
nodes:
    - id: GND
      type: ground
    - id: Vin
      type: input
    - id: Vo
      type: output
components: []
specs:
  find:
    - Expr(Vo, Vin, GND)
"""
    circuit = loads(yaml_text)
    res = validate(circuit)
    assert not res.is_valid
    assert any(e.code == "ERR_EXPR_INVALID_NODE_TYPE" for e in res.errors)


def test_validator_hf_illegal_on_dc_function():
    yaml_text = """
ceml_version: "0.1"
circuit_id: "vdc_hf"
nodes:
    - id: GND
      type: ground
    - id: N1
components: []
specs:
  find:
    - Vdc(N1, GND, hf)
"""
    circuit = loads(yaml_text)
    res = validate(circuit)
    assert not res.is_valid
    assert any(e.code == "ERR_INVALID_HF_ARGUMENT" for e in res.errors)


def test_validator_strict_mode_raises():
    yaml_text = """
ceml_version: "0.1"
circuit_id: "strict_err"
nodes:
    - id: N1
components: []
"""
    circuit = loads(yaml_text)
    with pytest.raises(CemlValidationError):
        validate(circuit, strict=True)


def test_validator_frequency_response_functions():
    yaml_text = """
ceml_version: "0.1"
circuit_id: "freq_resp_test"
nodes:
    - id: GND
      type: ground
    - id: Vin
      type: input
    - id: Vout
      type: output
components:
    - id: R1
      type: resistor
      value: R1
      pins: [Vin, Vout]
specs:
  find:
    - Fp(Vout, Vin)
    - Fz(Vout, Vin)
    - Wp(Vout, Vin)
    - Wz(Vout, Vin)
"""
    circuit = loads(yaml_text)
    res = validate(circuit)
    assert res.is_valid
    assert len(res.errors) == 0


def test_validator_frequency_response_invalid_arity():
    yaml_text = """
ceml_version: "0.1"
circuit_id: "freq_resp_bad_arity"
nodes:
    - id: GND
      type: ground
    - id: Vin
      type: input
components: []
specs:
  find:
    - Fp(Vin)
"""
    circuit = loads(yaml_text)
    res = validate(circuit)
    assert not res.is_valid
    assert any(e.code == "ERR_FREQUENCY_RESPONSE_ARITY" for e in res.errors)
