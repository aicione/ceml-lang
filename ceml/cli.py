"""CEML Command Line Interface.

Provides CLI commands for inspecting and validating .ci circuit description files.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional, Sequence

import ceml
from ceml.models import ValidationResult
from ceml.parser import CemlParseError

# ANSI Color codes for clean terminal output
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_CYAN = "\033[36m"


def _colorize(text: str, color_code: str, enable_color: bool = True) -> str:
    """Wraps text in ANSI color codes if enabled."""
    if not enable_color:
        return text
    return f"{color_code}{text}{COLOR_RESET}"


def _format_validation_report(
    path: Path,
    result: ValidationResult,
    enable_color: bool = True,
    verbose: bool = False,
) -> str:
    """Formats a ValidationResult into human-readable terminal output."""
    lines: list[str] = []
    header = f"Checking: {path.name}"
    lines.append(_colorize(header, COLOR_BOLD, enable_color))

    if result.is_valid:
        lines.append(_colorize("  [PASS] Circuit is valid", COLOR_GREEN, enable_color))
    else:
        lines.append(
            _colorize(
                f"  [FAIL] Validation failed with {len(result.errors)} fatal error(s):",
                COLOR_RED,
                enable_color,
            )
        )
        for err in result.errors:
            tag = _colorize(f"[{err.code}]", COLOR_RED, enable_color)
            lines.append(f"    - {tag} {err.message}")

    if result.warnings:
        lines.append(_colorize(f"  Warnings ({len(result.warnings)}):", COLOR_YELLOW, enable_color))
        for warn in result.warnings:
            tag = _colorize(f"[{warn.code}]", COLOR_YELLOW, enable_color)
            lines.append(f"    - {tag} {warn.message}")

    if result.suggestions and (verbose or not result.is_valid):
        lines.append(_colorize(f"  Suggestions ({len(result.suggestions)}):", COLOR_CYAN, enable_color))
        for sugg in result.suggestions:
            tag = _colorize(f"[{sugg.code}]", COLOR_CYAN, enable_color)
            lines.append(f"    - {tag} {sugg.message}")

    return "\n".join(lines)


def command_check(args: argparse.Namespace) -> int:
    """Handles the 'check' subcommand to validate one or more .ci files."""
    enable_color = not args.no_color and sys.stdout.isatty()
    target_paths: list[Path] = []

    for p_str in args.paths:
        p = Path(p_str)
        if not p.exists():
            print(
                _colorize(f"Error: Path not found: {p_str}", COLOR_RED, enable_color),
                file=sys.stderr,
            )
            return 1
        if p.is_dir():
            target_paths.extend(sorted(p.glob("*.ci")))
        else:
            target_paths.append(p)

    if not target_paths:
        print("No .ci files found to check.")
        return 0

    has_failures = False
    total_passed = 0
    total_failed = 0

    for path in target_paths:
        try:
            circuit = ceml.load(path)
            report = ceml.validate(circuit)
            print(_format_validation_report(path, report, enable_color=enable_color, verbose=args.verbose))
            print()
            if report.is_valid:
                total_passed += 1
            else:
                total_failed += 1
                has_failures = True
        except CemlParseError as exc:
            total_failed += 1
            has_failures = True
            print(_colorize(f"Checking: {path.name}", COLOR_BOLD, enable_color))
            print(_colorize(f"  [FAIL] Parse error: {exc}", COLOR_RED, enable_color))
            print()
        except Exception as exc:
            total_failed += 1
            has_failures = True
            print(_colorize(f"Checking: {path.name}", COLOR_BOLD, enable_color))
            print(_colorize(f"  [FAIL] Unexpected error: {exc}", COLOR_RED, enable_color))
            print()

    summary_color = COLOR_RED if has_failures else COLOR_GREEN
    summary = f"Summary: {total_passed} passed, {total_failed} failed (total: {len(target_paths)})"
    print(_colorize(summary, summary_color, enable_color))

    return 1 if has_failures else 0


def command_inspect(args: argparse.Namespace) -> int:
    """Handles the 'inspect' subcommand to display detailed circuit structure."""
    enable_color = not args.no_color and sys.stdout.isatty()
    p = Path(args.path)

    if not p.exists():
        print(
            _colorize(f"Error: Path not found: {args.path}", COLOR_RED, enable_color),
            file=sys.stderr,
        )
        return 1

    try:
        circuit = ceml.load(p)
    except Exception as exc:
        print(_colorize(f"Failed to load circuit: {exc}", COLOR_RED, enable_color), file=sys.stderr)
        return 1

    title = f"Circuit: {circuit.circuit_id} (CEML v{circuit.ceml_version})"
    print(_colorize(title, COLOR_BOLD, enable_color))
    if circuit.description:
        print(f"Description: {circuit.description}")
    print("-" * len(title))

    # Nodes
    print(_colorize(f"\nNodes ({len(circuit.nodes)}):", COLOR_CYAN, enable_color))
    for node in circuit.nodes.values():
        val_str = f" = {node.value.raw}V" if node.value else ""
        print(f"  - {node.id:8s} type: {node.type.value:<10s}{val_str}")

    # Components
    print(_colorize(f"\nComponents ({len(circuit.components)}):", COLOR_CYAN, enable_color))
    for comp in circuit.components.values():
        val_str = f"value={comp.value.raw}" if comp.value else ""
        beh_str = f"ac_behavior={comp.ac_behavior.value}" if comp.ac_behavior else ""
        role_str = f"role='{comp.role}'" if comp.role else ""
        pins_str = f"pins={comp.pins}"
        extras = ", ".join(s for s in [val_str, beh_str, role_str] if s)
        extra_display = f" ({extras})" if extras else ""
        print(f"  - {comp.id:8s} {comp.type:<16s} {pins_str}{extra_display}")

    # Specs
    if circuit.specs:
        print(_colorize("\nSpecs:", COLOR_CYAN, enable_color))
        if circuit.specs.given:
            print("  Given:")
            for item in circuit.specs.given:
                val = f": {item.value.raw}" if item.value else ""
                print(f"    - {item.target}{val}")
        if circuit.specs.find:
            print("  Find:")
            for item in circuit.specs.find:
                print(f"    - {item.target}")
    else:
        print(_colorize("\nSpecs: (none)", COLOR_YELLOW, enable_color))

    return 0


def build_parser() -> argparse.ArgumentParser:
    """Builds the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="ceml",
        description="Circuit Engineering Markup Language (CEML) Command Line Interface.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ceml {ceml.__version__}",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color formatting in output.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: check
    check_parser = subparsers.add_parser(
        "check",
        aliases=["validate"],
        help="Validate one or more .ci files against CEML specification rules.",
    )
    check_parser.add_argument(
        "paths",
        nargs="+",
        help="Path(s) to .ci file(s) or directories containing .ci files.",
    )
    check_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show suggestions and additional details even for passing circuits.",
    )
    check_parser.set_defaults(func=command_check)

    # Subcommand: inspect
    inspect_parser = subparsers.add_parser(
        "inspect",
        aliases=["info"],
        help="Display detailed components, nodes, and specs of a circuit.",
    )
    inspect_parser.add_argument(
        "path",
        help="Path to the .ci file to inspect.",
    )
    inspect_parser.set_defaults(func=command_inspect)

    # Subcommand: render
    render_parser = subparsers.add_parser(
        "render",
        aliases=["draw"],
        help="Render a 2D circuit schematic diagram (.png, .svg, or .pdf).",
    )
    render_parser.add_argument(
        "path",
        help="Path to the .ci file to render.",
    )
    render_parser.add_argument(
        "-o",
        "--output",
        help="Output image file path (defaults to <circuit_id>.png).",
    )
    render_parser.set_defaults(func=command_render)

    return parser


def command_render(args: argparse.Namespace) -> int:
    """Handles the 'render' subcommand to draw a circuit schematic to an image."""
    enable_color = not args.no_color and sys.stdout.isatty()
    p = Path(args.path)

    if not p.exists():
        print(
            _colorize(f"Error: Path not found: {args.path}", COLOR_RED, enable_color),
            file=sys.stderr,
        )
        return 1

    try:
        circuit = ceml.load(p)
    except Exception as exc:
        print(_colorize(f"Failed to load circuit: {exc}", COLOR_RED, enable_color), file=sys.stderr)
        return 1

    out_path = Path(args.output) if args.output else p.with_suffix(".png")

    try:
        from ceml.schematic import render_circuit
        render_circuit(circuit, out_path)
        print(_colorize(f"Schematic successfully generated: {out_path}", COLOR_GREEN, enable_color))
        return 0
    except ImportError as exc:
        print(
            _colorize(
                f"Error: Rendering requires 'schemdraw' and 'matplotlib'.\n"
                f"Install with: pip install 'ceml-lang[render]'",
                COLOR_RED,
                enable_color,
            ),
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(_colorize(f"Failed to render circuit schematic: {exc}", COLOR_RED, enable_color), file=sys.stderr)
        return 1



def main(argv: Optional[Sequence[str]] = None) -> int:
    """Main CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
