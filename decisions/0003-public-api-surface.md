# ADR 0003: Public API surface definition (`ceml.__init__`)

## Status
Accepted

## Context
The downstream AI.ciOne project requires a concise, predictable, and clean interface to load `.ci` files, convert them into in-memory structures, and validate them according to the CEML specification.

## Decision
Expose the following primary functions and classes at the package root level in `ceml/__init__.py`:
- `ceml.load(path: str | Path) -> Circuit`: Reads and converts a `.ci` file into a `Circuit` object.
- `ceml.loads(text: str) -> Circuit`: Parses and converts a CEML YAML string into a `Circuit` object.
- `ceml.validate(circuit: Circuit, strict: bool = False) -> ValidationResult`: Runs validation per specification v0.1 (§9), returning a structured report with fatal errors (`errors`), warnings (`warnings`), and suggestions (`suggestions`), as well as the boolean status `is_valid`.
- `Circuit`, `ValidationResult`, `ValidationError`, `ValidationWarning`: Core models and result types directly accessible to consumers.

## Consequences
- Integration with the AI.ciOne pipeline requires only `import ceml`, `circuit = ceml.load(...)`, and `report = ceml.validate(circuit)`.
- Internal implementation details (regex patterns, node/component extraction routines) remain private and encapsulated.
