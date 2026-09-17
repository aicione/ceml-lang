# Architecture Decision Records (ADRs)

This directory documents architectural and technical design decisions made for the `ceml-lang` Python library.

For language-level specification decisions (syntax, semantics, and reserved words), refer to **§10 Recorded design decisions** in [`spec/ceml-v0.1.md`](../spec/ceml-v0.1.md).

## Decision Index

| ID | Title | Status | Date |
|---|---|---|---|
| [0001](0001-internal-python-library-architecture.md) | Architecture as an internal parsing and validation library | Accepted | 2026-09-15 |
| [0002](0002-native-dataclasses-for-ast.md) | Adoption of native dataclasses for AST models | Accepted | 2026-09-15 |
| [0003](0003-public-api-surface.md) | Public API surface definition (`ceml.__init__`) | Accepted | 2026-09-15 |
| [0004](0004-testing-framework-and-virtualenv.md) | Adoption of pytest and virtual environment (`.venv`) | Accepted | 2026-09-15 |
| [0005](0005-cli-interface-and-entrypoints.md) | Command Line Interface (CLI) and Entrypoints | Accepted | 2026-09-16 |
| [0006](0006-frequency-response-and-symbolic-values.md) | Frequency-Response Functions and Symbolic Values (Decision #30) | Accepted | 2026-09-17 |
