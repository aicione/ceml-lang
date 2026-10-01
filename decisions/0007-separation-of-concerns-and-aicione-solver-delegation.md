# ADR 0007: Separation of Concerns, Dedicated Solver Repository (aicione), and Language Scope

## Status
Accepted

## Context
In the initial project roadmap, CEML was designed as a declarative circuit engineering markup language. As the mathematical solving requirements grew—including multi-regime DC operating point calculations, AC small-signal hybrid-$\pi$ extraction, node coalescing through coupling/bypass capacitors, and high-frequency Open-Circuit Time Constant (OCTC) analysis—a dedicated companion repository, `aicione`, was established to house the analytical solving engines (SymPy, matrix nodal equations, device linearization).

During late September 2026, substantial features and architectural milestones were implemented in `aicione` (documented across `aicione/decisions/0001` through `0010`), including:
- Small-signal AC hybrid-$\pi$ model AST extraction (ADR 0005, 0006, 0007 in `aicione`).
- Unified multi-regime solving pipeline (ADR 0008 in `aicione`).
- High-frequency internal capacitance modeling and AST extraction (ADR 0009 in `aicione`).
- Open-Circuit Time Constant (OCTC / Cochrun-Simpson) analytical pole/zero solver (ADR 0010 in `aicione`).

It is essential to formally establish and record the architectural boundary between `ceml-lang` and `aicione` within the `ceml-lang` documentation.

## Decision

1. **Strict Separation of Concerns**:
   - `ceml-lang` remains the authoritative specification and reference implementation for the **language syntax, parser, validator, AST models, and visual diagram compilation**. It does not perform symbolic circuit solving, Kirchhoff matrix formulation, or semiconductor physics calculations.
   - `aicione` acts as the downstream **computational reasoning engine**, consuming validated `ceml.models.Circuit` AST structures to formulate and solve analytical equations.

2. **Visual Rendering Ownership**:
   - Visual compilation—transforming `.ci` declarative netlists into standard 2D schematic diagrams (`.png`, `.svg`)—belongs within `ceml-lang`. Just as compilers for languages like Graphviz (`dot`) or Mermaid (`mmdc`) provide their own visual rendering backend, `ceml-lang` provides `ceml.schematic` and the `ceml render` CLI command.
   - `aicione` may consume `ceml.schematic` to overlay or annotate circuit diagrams with solved voltages, currents, and frequency pole/zero values.

## Consequences

- Keeps `ceml-lang` lightweight, deterministic, and free of heavy CAS dependencies like SymPy for users who solely need parsing, linting, validation, and visual rendering.
- Establishes a clean, single-direction dependency: `aicione` depends on `ceml-lang`, while `ceml-lang` has no runtime dependency on `aicione`.
- Clear maintenance boundary: language syntax and visualization evolve in `ceml-lang`; solving mathematics and device models evolve in `aicione`.
