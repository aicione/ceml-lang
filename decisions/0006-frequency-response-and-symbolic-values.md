# ADR 0006: Frequency-Response Functions and Explicit Symbolic Values (Decision #30)

## Status
Accepted

## Context
Real-world analog electronics course exams (specifically "Eletrônica III") frequently involve frequency response derivations, such as determining the dominant pole ($f_p, \omega_p$) or dominant zero ($f_z, \omega_z$) of an amplifier stage.

Furthermore, many academic exam problems are formulated purely symbolically or algebraically, providing no numerical values for passive components, bias supplies, or device parameters ($R_S, R_L, C_S, C_{ext}, g_m$). Prior to this decision, components without declared numerical values or `ac_behavior` were strictly treated as unknowns that must appear in `specs.find`, which caused false-positive validation errors for known symbolic parameters.

## Decision
1. **Reserved frequency-response functions**:
   - `Fp(Vout, Vin)`: dominant pole frequency in Hertz ($f_p$).
   - `Fz(Vout, Vin)`: dominant zero frequency in Hertz ($f_z$).
   - `Wp(Vout, Vin)`: dominant pole angular frequency in radians per second ($\omega_p$).
   - `Wz(Vout, Vin)`: dominant zero angular frequency in radians per second ($\omega_z$).
   Each function requires two node arguments: the output node and the input reference node. High-frequency transistor models are used implicitly.
2. **Explicit literal/symbolic component values**:
   - Formally support declaring literal variable names for component values (e.g., `value: RS`, `value: "RX"`).
   - A component with an explicit symbolic value is treated as a known parameter (satisfying the declared-value rule), distinguishing it from an unknown to be determined in `specs.find`.

## Consequences
- Purely symbolic and literal exam derivation problems can be transcribed accurately into CEML without fabricating numerical component values.
- Frequency-response metrics (dominant pole/zero) are first-class citizens in `specs.find`.
- Documented as Decision #30 in `spec/ceml-v0.1.md`.
