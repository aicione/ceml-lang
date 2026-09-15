# ADR 0004: Adoption of pytest and virtual environment (`.venv`)

## Status
Accepted

## Context
Developing the library requires an automated testing strategy to verify the robustness of both parser and validator against the specification (`spec/ceml-v0.1.md`) and real-world example circuits in `examples/*.ci`.
Furthermore, development dependencies (`pytest`) and runtime dependencies (`pyyaml`) must be managed reproducibly and in isolation without polluting or depending on system-wide Python packages.

## Decision
1. **Isolated local virtual environment**: Use a local Python virtual environment in the `.venv/` directory at the project root (ignored in `.gitignore`), containing `pytest` and `pyyaml`.
2. **Testing framework**: Adopt `pytest` as the official test runner for the project.
   - Provides clean assertion syntax with `assert`, reusable fixtures, parameterized tests, and informative failure diffs.
   - Natively supports testing modular components and running regression test suites.

## Consequences
- Local test runs are standardized via `.venv/bin/pytest`.
- The developer's host operating system environment remains unaffected.
