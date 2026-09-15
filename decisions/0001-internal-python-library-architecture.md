# ADR 0001: Architecture as an internal parsing and validation library

## Status
Accepted

## Context
The CEML project defines a declarative YAML-based markup language for analog circuit description and analytical reasoning. As formalized in design decisions #7 and #8 of the specification (`spec/ceml-v0.1.md`), the parser and validator should function as an internal Python library within the `ceml-lang` repository, acting as the primary ingestion layer for the AI.ciOne pipeline.

A clear separation of concerns was required within the `ceml-lang` codebase.

## Decision
Structure the codebase into three main modules under the `ceml/` package:
1. `ceml/models.py`: Strongly typed data structures representing circuit nodes, components, pinouts, parameters, and specifications (in-memory AST).
2. `ceml/parser.py`: Responsible for loading the `.ci` YAML file, normalizing engineering notation (e.g., `4k7`, `10n`), and instantiating AST models.
3. `ceml/validator.py`: Responsible for rigorous semantic and topological validation according to the v0.1 specification rules (§9), reporting fatal errors, warnings, and suggestions.

## Consequences
- The downstream analytical solver (AI.ciOne) is completely decoupled from file syntax and raw YAML layout.
- Semantic rules (fatal errors that invalidate the circuit, warnings about assumed defaults) are centralized in a reusable, independent validator.
