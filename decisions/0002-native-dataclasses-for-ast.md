# ADR 0002: Adoption of native dataclasses for AST models

## Status
Accepted

## Context
To represent circuit nodes, components, pinouts, and specifications in memory, we evaluated using third-party schema/validation libraries (such as Pydantic) versus Python's standard library `dataclasses`.

## Decision
Use Python's built-in `dataclasses` in `ceml/models.py`.

Rationale:
1. **Zero extra runtime dependencies**: Keeps the package dependent exclusively on `PyYAML` for parsing the file format.
2. **Performance and simplicity**: Deep semantic validation in CEML (electrical graph rules, AC/DC regime rules, cross-referencing nodes and parameters) is domain-specific and requires custom business logic regardless of attribute type checking.
3. **Immutability and clarity**: Clear, inspectable data structures that are simple to serialize or convert into downstream symbolic objects.

## Consequences
- Structural and semantic validation is the explicit responsibility of `ceml.validator` and `ceml.parser`.
- Lower maintenance overhead and minimal installation footprint for `ceml-lang`.
