# CEML Specification v0.1

**Circuit Engineering Markup Language**
Version: 0.1 — Work in progress
Project: AI.ciOne

---

## 1. Overview

CEML is a declarative YAML-based language for describing analog electronic circuits with a focus on analytical reasoning. CEML files use the `.ci` extension.

A `.ci` file is structured in the following order:

```
1. header      → circuit metadata
2. nodes       → node declarations
3. components  → component declarations
4. specs       → known parameters and unknowns
```

---

## 2. Header

```yaml
ceml_version: "0.1"       # required
circuit_id: "string"      # required, unique per project
description: "string"     # optional, human-readable description
```

---

## 3. Nodes

Every circuit must have at least one `ground` node.

```yaml
nodes:
    - id: GND
      type: ground

    - id: VCC
      type: supply
      value: 12        # V implicit

    - id: N1           # type omitted → inferred as internal

    - id: Vin
      type: input

    - id: Vout
      type: output

    - id: Vx
      type: bidir      # simultaneously input and output
```

### Valid node types

| type | Description |
|---|---|
| `ground` | Circuit reference (0V) |
| `supply` | DC supply voltage |
| `internal` | Intermediate node (default if omitted) |
| `input` | Signal input port |
| `output` | Signal output port |
| `bidir` | Simultaneously input and output |

### Rules
- `id` is required and must be unique throughout the file
- `type` omitted → automatically assumes `internal`
- Multiple nodes of the same type are allowed (e.g. VCC and VEE, Vin+ and Vin-)
- A node declared but not connected to any component generates a **warning**

---

## 4. Components

```yaml
components:
    - id: R1            # required, unique
      type: resistor    # required
      value: 47k        # Ω implicit — omitted if listed in find
      pins: [VCC, N1]   # required
      role: string      # optional — semantic context
```

### Fields

| Field | Required | Description |
|---|---|---|
| `id` | Yes | Unique identifier |
| `type` | Yes | Component type |
| `value` | Conditional | Required if not listed in `find` |
| `pins` | Yes | Connection to nodes |
| `model` | No | Transistor model |
| `role` | No | Semantic context |
| `ac_behavior` | No | Behavior in AC regime |
| `polarized` | No | Capacitors only — enforces p/n pin naming |

### Implicit units by type

| type | Implicit unit |
|---|---|
| `resistor` | Ω |
| `capacitor` | F |
| `inductor` | H |
| `voltage_source` | V |
| `current_source` | A |

### Accepted magnitude suffixes

`p, n, u, m, k, M, G` — standard engineering notation.

### Decimal notation

`.` (period) is the decimal separator, English/US convention — e.g. `0.7`, `4.7k`.
`,` (comma) is not accepted as a decimal separator.

### Valid component types

**Passives**
- `resistor`
- `capacitor`
- `inductor`

**Semiconductors**
- `BJT` — polarity: `NPN` or `PNP`
- `MOSFET` — polarity: `NMOS` or `PMOS`
- `JFET` — polarity: `N` or `P`
- `diode`

> `polarity` omitted → defaults to the most common convention per type (`NPN`, `NMOS`, `N`) with a **warning**. An invalid `polarity` value (not one of the type's two options) is a **fatal error**.

**Independent sources**
- `voltage_source` — regime: `DC` or `AC`
- `current_source` — regime: `DC` or `AC`

**Dependent sources**
- `VCVS` — voltage controlled voltage source
- `VCCS` — voltage controlled current source
- `CCVS` — current controlled voltage source
- `CCCS` — current controlled current source

**Complex components**
- `opamp`

### AC behavior

```yaml
ac_behavior: short_circuit    # bypass and coupling capacitors
ac_behavior: open_circuit     # choke inductors
```

> Capacitor blocks DC (open circuit) by default in every DC analysis, regardless of `ac_behavior` — this follows from the component's physics and needs no declaration.
> `ac_behavior` only overrides AC-regime behavior, for the case where the actual capacitance is assumed large enough to be treated as ideal (`C → ∞`, e.g. bypass/coupling capacitors).
> When `ac_behavior` is declared, `value` is no longer required — the declared behavior fully determines the component for analysis, so a numeric capacitance is not needed. `value` remains required (or must appear in `find`) when `ac_behavior` is absent.

### Source regime

```yaml
regime: DC    # biasing / quiescent-point source
regime: AC    # signal source
```

> `regime` is required on every `voltage_source` and `current_source` — absent or invalid `regime` on these types is a **fatal error**.
> `regime: DC` → the source is used in DC/quiescent analysis at its declared `value`; in AC small-signal analysis it contributes nothing (`voltage_source` becomes a short, `current_source` becomes an open), same convention as an ideal DC supply node.
> `regime: AC` → the source is used in AC small-signal analysis at its declared `value`; in DC/quiescent analysis it contributes nothing (`voltage_source` becomes a short, `current_source` becomes an open).
> This is the formal basis for superposition between the DC and AC domains — every independent source counts in exactly one regime, never both.

---

## 5. Pinout

### General rule for passives

```
polarized: true   → pins must use {p, n} naming
polarized: false  → pins use simple list [NODE_A, NODE_B]
polarized omitted → assumes false → simple list
```

> `polarized: true` is invalid for `resistor` and `inductor` — fatal error.

```yaml
# resistor — simple list, order does not matter
- id: R1
  type: resistor
  value: 47k
  pins: [VCC, N1]

# non-polarized capacitor — simple list
- id: C1
  type: capacitor
  value: 10n
  pins: [N1, N2]

# polarized capacitor — p/n required
- id: CE
  type: capacitor
  value: 100u
  polarized: true
  pins:
    p: N1
    n: GND
```

### Fixed terminals by type

| Type | Terminals |
|---|---|
| `diode` | `p`, `n` |
| `voltage_source` | `p`, `n` |
| `current_source` | `p`, `n` |
| `BJT` | `base`, `collector`, `emitter` |
| `MOSFET`, `JFET` | `gate`, `drain`, `source` |
| `opamp` | `in+`, `in-`, `out` required — `vcc`, `vee` optional |
| `VCVS`, `VCCS`, `CCVS`, `CCCS` | `pins: [NODE_A, NODE_B]` + `control: {type, pins}` |

> Diode: `p` = anode and `n` = cathode internally in the LLM.
> OpAmp: `vcc` and `vee` omitted → LLM assumes ideal supply and warns the user.

### Dependent sources

```yaml
- id: Gm1
  type: VCCS
  gain: gm
  pins: [N_drain, N_source]    # where the source is physically connected
  control:
    type: voltage              # voltage or current
    pins: [N_gate, N_source]   # what it is measuring
```

---

## 6. Transistor models

### Precedence hierarchy

```
1. Explicit parameters in the .ci file   → uses exactly what was declared
2. Transistor part number (e.g. BC548B)  → looks up internal database
3. Neither provided                      → assumes default values + warns user
```

### Default values

**BJT NPN/PNP**

| Parameter | Default |
|---|---|
| β (hfe) | 100 |
| VBE | 0.7V |
| VA | 100V |

> If VA is not declared → ro → ∞, user is warned.
> If explicitly declared as `ro: ignored` → ro → ∞ without warning.

**MOSFET NMOS/PMOS** — default values to be defined in v0.2

**JFET** — default values to be defined in v0.2

---

## 7. Specs

```yaml
specs:
  given:
    - Av: -100
    - Rin: 10k
    - freq: 1k

  find:
    - RC
    - RE
    - Vout
    - Zin(NODE_A, NODE_B)
    - Zt(Vout, Iin)
```

### Rules for unknowns

- A component without a declared `value` **must** appear in `find` — otherwise it is a **fatal error**
- Any behavioral parameter can appear in either `given` or `find`
- Symbolic expressions are valid in `value` and `given`: e.g. `"2 * R1"`

---

## 8. Reserved words and functions

### Reserved node
```
GND    → always the circuit ground, cannot be used as a free name
```

### Reserved measurement functions
```
Vdc(A, B)       → DC / quiescent voltage of A with respect to B
Vac(A, B)       → AC / small-signal voltage of A with respect to B
Idc(A, B)       → DC / quiescent current flowing from A to B
Iac(A, B)       → AC / small-signal current flowing from A to B
Idc(COMP)       → DC / quiescent current through component COMP
Iac(COMP)       → AC / small-signal current through component COMP
Z(A, B)         → impedance between nodes A and B
```
> Regime is part of the function name, not an argument — there is no bare `V(A,B)` or `I(A,B)`/`I(COMP)`. This removes the ambiguity of which regime a plain measurement refers to.
> `Z(A, B)` has no DC/AC variant — impedance is inherently an AC small-signal concept in CEML, same as `Zin`/`Zout`.

### Reserved behavioral functions
```
Av(Vout, Vin)       → voltage gain
Ai(Iout, Iin)       → current gain
Rin(NODE_A, NODE_B) → input resistance seen between two nodes
Rout(NODE_A, NODE_B)→ output resistance seen between two nodes
Zin(NODE_A, NODE_B) → input impedance seen between two nodes
Zout(NODE_A, NODE_B)→ output impedance seen between two nodes
Zt(Vout, Iin)       → transimpedance (V/A)
Yt(Iout, Vin)       → transconductance (A/V)
```

### Reserved transistor internal parameter functions
```
Vbe(Q)    Vce(Q)    Vbc(Q)    → BJT internal voltages
Vgs(Q)    Vds(Q)    Vgd(Q)    → MOSFET/JFET internal voltages
Ic(Q)     Ib(Q)     Ie(Q)     → BJT internal currents
Id(Q)     Ig(Q)     Is(Q)     → MOSFET/JFET internal currents
hfe(Q)                        → BJT current gain (β)
```
> `Ig(Q)` is reserved but the LLM always assumes 0 for MOSFET/JFET — may be revised in future versions if needed.
> `hfe(Q)` may appear in `given` (when the question states β explicitly) or in `find` (when β is the unknown). If absent from both, the default value applies (§6).
> All functions in this section are DC / quiescent operating-point values by definition (`Ic(Q)` is the quiescent collector current ICQ, `Vce(Q)` is VCEQ, etc.) — there is no AC/small-signal variant of these, unlike `Vdc`/`Vac`/`Idc`/`Iac` above. This matches standard textbook convention: these symbols always denote the bias point used to linearize the small-signal model, never the incremental AC component.

### Reserved commercial value function
```
Commercial(COMPONENT)
Commercial(COMPONENT, mode)
Commercial(COMPONENT, series)
Commercial(COMPONENT, mode, series)
```
> Rounds the calculated theoretical value of `COMPONENT` to a standard value in `series`, per the constraint from `mode`.
> `mode` (optional): `min` (round up — smallest commercial value ≥ theoretical value) | `max` (round down — largest commercial value ≤ theoretical value) | `nearest` — defaults to `nearest` when omitted.
> `series` (optional): `E12` | `E24` | `E48` | `E96` — defaults to `E12` (RETMA R12: 10-12-15-18-22-27-33-39-47-56-68-82) when omitted.
> `mode` and `series` may appear in either order after `COMPONENT` — each is matched by which of the two fixed token sets it belongs to, not by position.
> Only valid in `find`, and only for a component whose theoretical value would otherwise be computed symbolically/numerically.

### Reserved two-port parameter functions
```
Zparam(i,j)     → Zij parameter of the impedance matrix
Yparam(i,j)     → Yij parameter of the admittance matrix
Hparam(i,j)     → Hij parameter of the hybrid matrix
Gparam(i,j)     → Gij parameter of the inverse hybrid matrix
ABCD(i,j)       → parameter of the transmission matrix
```
> `Zparam`, `Yparam`, `Hparam`, `Gparam` and `ABCD` take integer indices `i,j ∈ {1,2}` — unlike `Z(A,B)` which takes circuit nodes.
> `ABCD(i,j)` only accepts `(1,1)`, `(1,2)`, `(2,1)`, `(2,2)` corresponding to the positions of the 2x2 transmission matrix.

### General rules
- Free names in `find` cannot match any reserved word or function
- Reserved functions require mandatory parameters — using without parameters is a **fatal error**
- Direction always implicit: looking into the circuit from the declared nodes

---

## 9. Validation

### Fatal errors — prevent analysis
- Duplicate IDs
- Invalid or nonexistent `type`
- Component referencing an undeclared node
- No `ground` node declared
- Required pin not connected
- `value` absent from component not listed in `find`, unless `ac_behavior` is declared (§4)
- `polarized: true` on `resistor` or `inductor`
- `regime` absent or invalid on `voltage_source` or `current_source`
- `polarity` present but not a valid option for the component's type
- Reserved function used without mandatory parameters

### Warnings — analysis continues, user is notified
- Transistor without parameters → assumes default values (Decision #1)
- VA absent in BJT → ro → ∞ (Decision #2)
- `polarity` absent on `BJT`/`MOSFET`/`JFET` → assumes `NPN`/`NMOS`/`N` (Decision #21)
- `vcc` and `vee` absent in `opamp` → ideal supply assumed
- Node declared but not connected to any component
- No `input` or `output` node declared

### Suggestions — best practices
- Circuit without a `specs` section
- Component without a `role` field

---

## 10. Recorded design decisions

| # | Decision |
|---|---|
| 1 | Transistor parameter hierarchy: explicit > part number > default |
| 2 | VA absent → ro → ∞ with warning; `ro: ignored` → no warning |
| 3 | Unknown = absent value + present in find; absent without find = fatal error; symbolic expressions valid in value |
| 4 | Implicit units by component type |
| 5 | Specs section with given and find |
| 6 | Node type omitted → internal; multiple nodes of same type allowed |
| 7 | Validator is an internal Python library inside ceml-lang |
| 8 | Validator integrated into the AI.ciOne pipeline |
| 9 | Passives without polarity → simple list; with polarized: true → p/n required |
| 10 | Dependent sources have physical pins + separate control block |
| 11 | Diode: p = anode, n = cathode internally in the LLM |
| 12 | Fixed terminals by type; polarized: true invalid for resistor and inductor |
| 13 | Reserved words and functions in given/find; Ig(Q) = 0 by default; two-port indices i,j ∈ {1,2} |
| 14 | Capacitor with `ac_behavior` declared → `value` no longer required; capacitor always opens in DC by default |
| 15 | `hfe(Q)` reserved for BJT β — valid in `given` or `find` |
| 16 | `Commercial(COMPONENT, mode?, series?)` reserved — rounds a `find` result to an E12/E24/E48/E96 value; mode defaults to nearest, series defaults to E12 |
| 17 | `.` (period) is the only accepted decimal separator |
| 18 | Transistor internal parameter functions (Vbe(Q), Ic(Q), etc.) are always DC/quiescent by definition — no AC variant |
| 19 | V(A,B)/I(A,B)/I(COMP) replaced by regime-qualified Vdc/Vac/Idc/Iac — regime is part of the function name, not an argument |
| 20 | `regime` required on voltage_source/current_source — DC source is zeroed in AC analysis and vice versa (superposition basis); absent/invalid regime is a fatal error |
| 21 | `polarity` omitted → defaults to NPN/NMOS/N with a warning; invalid `polarity` value is a fatal error |

---

*Specification under active development — subject to changes until v1.0*
