"""Unit tests for CEML schematic rendering and SchemDraw mapping (ADR 0008)."""

from pathlib import Path
import pytest

import ceml
from ceml.cli import main as cli_main
from ceml.schematic import create_schematic_drawing, plan_circuit_layout, render_circuit


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent.parent.parent / "aicione" / "tests" / "fixtures"


@pytest.fixture
def examples_dir() -> Path:
    return Path(__file__).parent.parent / "examples"


@pytest.fixture
def output_dir() -> Path:
    out = Path(__file__).parent / "output"
    out.mkdir(parents=True, exist_ok=True)
    return out


def test_plan_circuit_layout_bjt_amplifier(fixtures_dir: Path):
    """Verifies layout planning for a single-stage BJT common-emitter amplifier."""
    ci_path = fixtures_dir / "bjt_amplifier.ci"
    circuit = ceml.load(ci_path)
    plan = plan_circuit_layout(circuit)

    assert plan.is_active_amplifier is True
    assert len(plan.stages) == 1

    stage = plan.stages[0]
    assert stage.is_bjt is True
    assert len(stage.base_gate_pullup) == 1
    assert len(stage.base_gate_pulldown) == 1
    assert len(stage.collector_drain_pullup) == 1
    assert len(stage.emitter_source_pulldown) == 1
    assert len(stage.input_chain) == 1
    assert len(stage.output_chain) == 1
    assert len(stage.load_components) == 1



def test_render_bjt_amplifier_to_png_and_svg(fixtures_dir: Path, output_dir: Path):
    """Verifies that render_circuit produces valid PNG and SVG files for BJT amplifier."""
    ci_path = fixtures_dir / "bjt_amplifier.ci"
    circuit = ceml.load(ci_path)

    png_out = output_dir / "bjt_amp.png"
    svg_out = output_dir / "bjt_amp.svg"

    render_circuit(circuit, png_out)
    render_circuit(circuit, svg_out)

    assert png_out.exists()
    assert png_out.stat().st_size > 1000
    assert svg_out.exists()
    assert svg_out.stat().st_size > 500


def test_render_common_gate_nmos(fixtures_dir: Path, output_dir: Path):
    """Verifies rendering for Common Gate NMOS amplifier (cg_nmos_freq_response.ci)."""
    ci_path = fixtures_dir / "cg_nmos_freq_response.ci"
    circuit = ceml.load(ci_path)

    plan = plan_circuit_layout(circuit)
    assert plan.is_active_amplifier is True
    stage = plan.stages[0]
    assert stage.is_nmos is True
    assert stage.input_pin_name == "source"
    assert len(stage.input_chain) == 2  # R_gen, C2
    assert len(stage.base_gate_pulldown) == 1  # R2
    assert len(stage.base_gate_bypass) == 1  # C1

    out_file = output_dir / "cg_nmos.png"
    render_circuit(circuit, out_file)
    assert out_file.exists()
    assert out_file.stat().st_size > 1000


def test_render_ce_partial_bypass(examples_dir: Path, output_dir: Path):
    """Verifies rendering for CE amplifier with partially bypassed emitter resistor."""
    ci_path = examples_dir / "ce_partial_bypass_coupled_load.ci"
    circuit = ceml.load(ci_path)

    plan = plan_circuit_layout(circuit)
    stage = plan.stages[0]
    assert len(stage.emitter_source_bypass) == 1
    assert len(stage.emitter_source_bypass[0]) == 2  # C3 + R1

    out_file = output_dir / "ce_partial.png"
    render_circuit(circuit, out_file)
    assert out_file.exists()
    assert out_file.stat().st_size > 1000


def test_render_passive_rlc_series(examples_dir: Path, output_dir: Path):
    """Verifies rendering for passive single-loop RLC circuit."""
    ci_path = examples_dir / "rlc_series.ci"
    circuit = ceml.load(ci_path)

    plan = plan_circuit_layout(circuit)
    assert plan.is_active_amplifier is False
    assert len(plan.passive_chain) == 4

    out_file = output_dir / "rlc.png"
    render_circuit(circuit, out_file)
    assert out_file.exists()
    assert out_file.stat().st_size > 500


def test_cli_render_command(fixtures_dir: Path, output_dir: Path):
    """Verifies that 'ceml render' CLI command executes cleanly with exit code 0."""
    ci_path = str(fixtures_dir / "bjt_amplifier.ci")
    out_file = str(output_dir / "cli_rendered.png")

    exit_code = cli_main(["render", ci_path, "-o", out_file])
    assert exit_code == 0
    assert Path(out_file).exists()
