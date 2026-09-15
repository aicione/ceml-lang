# AGENTS.md

Instructions for any coding agent (Claude Code, Codex, or similar) working in this repository.

## Project status

CEML is in **spec-first development**. As of now:
- `spec/ceml-v0.1.md` — actively maintained, the single source of truth for the language.
- `examples/*.ci` — worked examples, used to stress-test the spec before any code exists.
- `ceml/parser.py`, `ceml/validator.py`, `ceml/models.py` — **not implemented yet**. Do not
  start writing these unless explicitly asked; the current phase is spec validation via examples.

Do not treat `spec/ceml-v0.1.md` as frozen. It changes weekly as gaps are found. Always read it
fresh before answering questions about the language — don't rely on prior conversation summaries
of it.

## Working method — read this before touching examples/

Examples are **not invented from textbooks**. They are transcribed from  Brazilian "Eletrônica III" course material. This has two consequences:

1. **Never fabricate circuit values.** If a `.ci` file has a `nodes`/`components`/`specs` section
   with `# TODO` placeholders, that's deliberate — the human is going to fill in real component
   values from the exam question. Do not invent resistor/capacitor values, bias points, or
   circuit topology details that weren't given to you.
2. **When given only a topology description** (prose describing the circuit, no numeric values),
   the expected action is narrow: rename the file to a descriptive `circuit_id`-style name, set
   `circuit_id` and `description` to match, and leave `nodes:`/`components:`/`specs:` as the TODO
   skeleton. Do not build out the full node/component graph unless explicitly asked to.
3. **When reviewing a filled-in example**, validate it line by line against the current
   `spec/ceml-v0.1.md` (required fields, fatal-error rules, warnings) and flag anything that
   looks like a typo or omission — don't silently fix ambiguous cases (e.g. an unclear component
   value); ask or flag instead.

Every time a new example surfaces something the spec doesn't cover, that gap gets formalized as a
new **Recorded design decision** in `spec/ceml-v0.1.md` §10 (sequential numbering), with the
actual rule written into the relevant section (§4 Components, §5 Pinout, §6 Transistor models,
§8 Reserved words, or §9 Validation). This is the core feedback loop of the project — two example
circuits so far produced 11 new decisions (14–24). Expect this to keep happening.

## Language convention

Everything in this repository must be written in **English**:
- All source code, identifiers, types, and module names.
- All code comments and docstrings.
- All documentation, ADRs in `decisions/`, specification documents in `spec/`, and READMEs.
- All commit messages (`feat(...)`, `fix(...)`, etc.).
- All circuit metadata (`description` fields in `.ci` files).

Even though the source course material originates from Brazilian Portuguese "Eletrônica III", no Portuguese text should appear in repository code, comments, or documentation.

## File and naming conventions

- Placeholder examples are named `example_N.ci` (numbered stub, only a header + TODO skeleton)
  until their topology is known. Once described, rename to a descriptive snake_case name that
  reflects the topology (e.g. `ce_partial_bypass_coupled_load.ci`, `cc_dual_supply_current_bias.ci`,
  `cc_npn_cb_pnp_cascade.ci`) — never leave a finished example named `example_N.ci`.
- `circuit_id` always matches the filename (without `.ci`).
- `description` is in English, one sentence, naming the topology and its distinguishing traits
  (bias scheme, coupling, supply configuration) — not a generic restatement of the component list.

### YAML indentation (deliberate, do not "clean up")

`nodes:` and `components:` list items are indented **4 spaces** before the `-`, with nested keys
2 further spaces (6 total) — chosen because it's one tab-press, easier to type consistently by
hand than a 2-space list marker:  

```yaml
nodes:
    - id: GND
      type: ground
    - id: VCC
      type: supply
      value: 12
```

`specs:` keeps `given:`/`find:` at 2-space indent, with list items at 4-space indent (this one
is NOT 4-space at the top level — don't unify it with nodes/components):

```yaml
specs:
  given:
    - hfe(Q1): 200
  find:
    - Ic(Q1)
```

This same convention applies to the embedded YAML examples inside `spec/ceml-v0.1.md` and
`README.md` — keep them in sync with `examples/*.ci` style.

### Decimal notation

`.` (period) only. Never `,`. This applies everywhere a number appears in a `.ci` file.

## Spec conventions worth knowing before editing `spec/ceml-v0.1.md`

- Every new reserved function or field goes through the same checklist: define it where it's
  introduced (§4/§5/§6/§8), add the fatal-error or warning rule to §9 if it has one, and add a
  one-line entry to the Recorded design decisions table in §10.
- Regime (DC vs AC) is never an implicit default guessed from context — it's always an explicit,
  named token: `regime: DC|AC` on sources (Decision 20), `Vdc/Vac/Idc/Iac` instead of ambiguous
  `V()/I()` (Decision 19), and the optional `hf` argument for mid-band vs high-frequency model
  selection on AC/small-signal functions (Decision 23). Follow this pattern — don't introduce a
  new ambiguity that has to be inferred rather than declared.
- Defaults are only added when there's a genuinely standard convention (e.g. NPN/NMOS/N for
  omitted polarity, Decision 21). When there isn't one (e.g. `Cpi(Q)`/`Cmu(Q)`), the rule is:
  absent → ignored with a warning, never a guessed numeric default.
- `given` and `find` accept reserved functions bound to a component id (e.g. `hfe(Q1): 200`,
  `find: - Ic(Q1)`) — per-transistor parameters are not component-level YAML fields.

## Git conventions

- Remote uses SSH (`git@github.com:aicione/ceml-lang.git`), not HTTPS — keep it that way, it
  avoids credential prompts.
- Never commit unless explicitly asked. When asked, spec changes and example changes are
  typically committed separately, one commit per logical change.
- Commit messages follow Conventional Commits (`feat(spec): ...`, `feat(examples): ...`), title
  under ~70 chars, with a bullet-point body referencing the Decision numbers involved when
  editing the spec.
- Watch out for `git add` on `examples/` sweeping up unfinished `example_N.ci` stubs alongside a
  finished example that's ready to commit — add finished files by exact name.
