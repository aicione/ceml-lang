"""Tests for CEML CLI commands."""

from pathlib import Path
import pytest
from ceml.cli import main

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "ceml 0.1.0" in captured.out


def test_cli_check_valid_file(capsys):
    file_path = str(EXAMPLES_DIR / "ce_partial_bypass_coupled_load.ci")
    exit_code = main(["--no-color", "check", file_path])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "[PASS] Circuit is valid" in captured.out
    assert "Summary: 1 passed, 0 failed" in captured.out


def test_cli_check_failing_file(capsys):
    file_path = str(EXAMPLES_DIR / "rlc_series.ci")
    exit_code = main(["--no-color", "check", file_path])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "[FAIL] Validation failed" in captured.out
    assert "ERR_MISSING_VALUE_NOT_IN_FIND" in captured.out
    assert "Summary: 0 passed, 1 failed" in captured.out


def test_cli_check_directory(capsys):
    dir_path = str(EXAMPLES_DIR)
    exit_code = main(["--no-color", "check", dir_path])
    # Fails because rlc_series.ci is an expected invalid limit case
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "1 failed" in captured.out
    assert "passed" in captured.out


def test_cli_check_nonexistent_file(capsys):
    exit_code = main(["--no-color", "check", "non_existent_file.ci"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Path not found" in captured.err


def test_cli_inspect_valid_file(capsys):
    file_path = str(EXAMPLES_DIR / "three_opamp_multi_input.ci")
    exit_code = main(["--no-color", "inspect", file_path])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Circuit: three_opamp_multi_input" in captured.out
    assert "Nodes (13):" in captured.out
    assert "Components (14):" in captured.out
    assert "Expr(Vo, Vin1, Vin2, Vin3)" in captured.out


def test_cli_inspect_nonexistent_file(capsys):
    exit_code = main(["--no-color", "inspect", "non_existent_file.ci"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Path not found" in captured.err
