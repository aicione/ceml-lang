# ceml-lang

**CEML - Circuit Engineering Markup Language**

The intermediary language of the project [AI.ciOne](https://github.com/aicione/aicione) to represent analytically electronic circuits.

---

## What is the CEML ?

CEML is a declarative language to describe electronic circuits so that a LLM can analytically reason about it - not only numerically simulate.

CEML's files use the extension `.ci`

```yaml
ceml_version: "0.1"
circuit_id: "ce_amplifier_01"
description: "BJT NPN Amplifier in common emitter form"
 
nodes:
    - id: GND
      type: ground
    - id: VCC
      type: supply
      value: 12
    - id: N1
    - id: N2
    - id: Vin
      type: input
    - id: Vout
      type: output
 
components:
    - id: RC
      type: resistor
      value: 4k7
      pins: [VCC, N1]
    - id: RB
      type: resistor
      value: 47k
      pins: [VCC, N2]
    - id: Q1
      type: BJT
      polarity: NPN
      pins:
        base: N2
        collector: N1
        emitter: GND
 
specs:
  given:
    - freq: 1k
  find:
    - Av(Vout, Vin)
    - Rin(Vin, GND)
    - Rout(Vout, GND)
```
---

## Why not use SPICE (Language used in LTSpice)?

The SPICE was designed for numeric simulation, not for analytic reasoning. It doesn't distinguish DC Polarization from small-signal AC model, doesn't differentiate semantically components with distinct roles (like coupling and bypass capacitors), and doesn't work with symbolic incognites. The pipeline are always `CIRCUIT → NUMBERS`, while CEML permits also `PROJECT SPECIFICATIONS → CIRCUIT → SYMBOLIC EXPRESSIONS`

---

## Scope: what CEML/AI.ciOne is (and isn't) for

CEML's job is to **document a circuit** — topology, knowns, and unknowns. It makes no claim
that every circuit written in CEML is solvable.

AI.ciOne's job is to **solve well-posed problems that converge to a definite result** —
find the value(s) listed in `find`, given the circuit and the values in `given`. It is not
meant to perform open-ended feasibility or justification analysis (e.g. "is it possible to
determine R from this data? justify your answer") — a common style of exam question, but out
of scope here. If a circuit's `find` targets are underdetermined by its `given` data, that's a
property of the exam question, not something CEML/AI.ciOne is meant to route around or explain qualitatively.

See `examples/rlc_series.ci` for a worked case: only the AC voltage magnitudes across R, L
and C are given (no source amplitude, frequency, or phase) — enough to solve for the source's
amplitude via the phasor voltage triangle, but not enough to solve for R, L, or C individually.
That file deliberately leaves R, L, C without a value and out of `find`, which fails CEML's own
validation rule (§9) — that failure is intentional, not a bug.

**MVP scope note:** the MVP targets circuits with a single, well-posed solution — `given` fully
determines every `find` target, no ambiguity. Circuits that admit multiple valid solutions (a
real possibility once solving tools exist downstream) are explicitly out of scope for now. If the
solvable-circuit approach proves out and the project moves past MVP, multiple-solution handling
is the natural next frontier to tackle — not before.

---

## Repository Structure

```
ceml-lang/
├── spec/
│   └── ceml-v0.1.md        ← complete formal specification of the language
├── examples/
│   └── ce_amplifier.ci     ← real circuits examples (soon)
├── ceml/
│   ├── parser.py           ← read the .ci file and transform in data structure
│   ├── validator.py        ← verify mistakes, alerts and suggestions
│   └── models.py           ← dataclasses/Pydantic of components and nodes
├── LICENSE
└── README.md
```

---

## Supported Components

**Passives:** `resistor`, `capacitor` and `inductor`

**Semiconductors:** `BJT` (NPN/PNP), `MOSFET` (NMOS/PMOS), `JFET` (N/P), `diode`
 
**Independent Sources:** `voltage_source`, `current_source` (DC or AC)
 
**Dependent Sources:** `VCVS`, `VCCS`, `CCVS`, `CCCS`
 
**Complex components:** `opamp`
 
---
 
## Status
 
> Project in active specification — v0.1 in construction
 
Part of project [AI.ciOne](https://github.com/aicione/aicione).
 
---
 
## License
 
MIT License — see [LICENSE](./LICENSE).
 
