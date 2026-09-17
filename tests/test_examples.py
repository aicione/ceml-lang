"""Tests running parser and validator against real-world .ci examples."""

from pathlib import Path
import pytest
import ceml

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def test_example_ce_partial_bypass_coupled_load():
    ci_path = EXAMPLES_DIR / "ce_partial_bypass_coupled_load.ci"
    circuit = ceml.load(ci_path)
    report = ceml.validate(circuit)

    assert report.is_valid, f"Unexpected errors: {[e.message for e in report.errors]}"
    assert len(report.errors) == 0


def test_example_cc_dual_supply_current_bias():
    ci_path = EXAMPLES_DIR / "cc_dual_supply_current_bias.ci"
    circuit = ceml.load(ci_path)
    report = ceml.validate(circuit)

    assert report.is_valid, f"Unexpected errors: {[e.message for e in report.errors]}"
    assert len(report.errors) == 0


def test_example_cc_npn_cb_pnp_cascade():
    ci_path = EXAMPLES_DIR / "cc_npn_cb_pnp_cascade.ci"
    circuit = ceml.load(ci_path)
    report = ceml.validate(circuit)

    assert report.is_valid, f"Unexpected errors: {[e.message for e in report.errors]}"
    assert len(report.errors) == 0


def test_example_three_opamp_multi_input():
    ci_path = EXAMPLES_DIR / "three_opamp_multi_input.ci"
    circuit = ceml.load(ci_path)
    report = ceml.validate(circuit)

    assert report.is_valid, f"Unexpected errors: {[e.message for e in report.errors]}"
    assert len(report.errors) == 0


def test_example_cd_fet_source_follower_freq_response():
    ci_path = EXAMPLES_DIR / "cd_fet_source_follower_freq_response.ci"
    circuit = ceml.load(ci_path)
    report = ceml.validate(circuit)

    assert report.is_valid, f"Unexpected errors: {[e.message for e in report.errors]}"
    assert len(report.errors) == 0


def test_example_rlc_series_expected_failure():
    """rlc_series.ci is a known limit case that MUST fail validation per spec §9.

    R, L, and C are intentionally missing 'value' and not in 'find'.
    """
    ci_path = EXAMPLES_DIR / "rlc_series.ci"
    circuit = ceml.load(ci_path)
    report = ceml.validate(circuit)

    assert not report.is_valid
    missing_val_errors = [e for e in report.errors if e.code == "ERR_MISSING_VALUE_NOT_IN_FIND"]
    # R, L, and C should all fail with this error
    failed_comps = {e.component_id for e in missing_val_errors}
    assert failed_comps == {"R", "L", "C"}
