# ADR 0005: Command Line Interface (CLI) and Entrypoints

## Status
Accepted

## Context
Developers, automated scripts, and CI/CD pipelines require a fast and ergonomic way to inspect and validate `.ci` files directly from the shell without writing custom Python scripts.

## Decision
1. **Lightweight CLI with standard library `argparse`**: Implement the CLI in `ceml/cli.py` using Python's built-in `argparse` module, avoiding external dependencies (such as `click` or `typer`).
2. **Dual execution entrypoints**:
   - Executable module via `ceml/__main__.py`: allows invocation via `python -m ceml <subcommand>`.
   - Console script via `[project.scripts]` in `pyproject.toml`: provides the direct `ceml` binary command when the package is installed.
3. **Core Subcommands**:
   - `ceml check <paths...>` (alias `validate`): Validates one or multiple `.ci` files or directories. Outputs colored status indicators (errors, warnings, suggestions) and returns an exit code `0` on success or `1` on fatal errors.
   - `ceml inspect <path>` (alias `info`): Summarizes circuit structure, listing node types, component details, and specs.

## Consequences
- Single-command circuit verification is accessible in 1 second from any terminal.
- Shell exit codes (`0` vs `1`) allow direct integration into automated git pre-commit hooks and CI/CD pipelines.
- Terminal formatting uses non-intrusive ANSI codes with automatic TTY detection and an explicit `--no-color` override.
