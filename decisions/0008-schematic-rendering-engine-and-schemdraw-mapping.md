# ADR 0008: Visual Schematic Rendering Engine and SchemDraw Mapping (ceml.schematic)

## Status
Accepted

## Context
CEML defines analog electronic circuits as declarative netlists (nodes, active devices, passive components, and pin interconnections). While this textual AST is optimal for parsing, validating, and symbolic mathematical solving, human circuit designers and engineering students rely heavily on graphical 2D schematic diagrams.

Converting a declarative netlist into an aesthetically pleasing, publication-grade schematic presents an Electronic Design Automation (EDA) challenge:
- CEML `.ci` files do not specify manual $(x, y)$ coordinates for components.
- Unconstrained graph auto-layout (such as force-directed or generic planar graph algorithms) produces disordered "spaghetti" schematics that violate fundamental electrical conventions (e.g., ground placed at the top, diagonal passives, inverted transistors).
- In analog amplifier design (and standard textbook material such as Sedra & Smith and Eletrônica III course material), circuits adhere to a **strict canonical geometry**:
  - Positive power rails ($V_{CC}, V_{DD}$) on top.
  - Ground (`GND`) or negative rails on the bottom.
  - Signal flow strictly left-to-right (input on the far left, output on the far right).
  - Transistors centered vertically, with collector/drain branches extending UP and emitter/source branches extending DOWN.

The Python library `schemdraw` provides standard IEEE/ANSI electronic symbol primitives with support for vector (SVG, PDF) and raster (PNG) image backends.

## Decision

1. **Location in `ceml-lang`**:
   - The visual layout and rendering engine is implemented directly within `ceml-lang` under `ceml.schematic`.
   - Exposed via the `ceml render` CLI command.
   - Configured as an optional dependency group in `pyproject.toml` (`[project.optional-dependencies] render = ["schemdraw>=0.20", "matplotlib>=3.8"]`).

2. **Hierarchical Column-Based Analog Layout Algorithm**:
   - **Phase 1: Electrical Role Identification**:
     - `Supply Rails`: Nodes of `type: supply` (or fixed positive potentials) are assigned to the top horizontal rail ($y = Y_{top}$).
     - `Ground / Negative Rails`: Nodes of `type: ground` (or negative rails) are assigned to the bottom horizontal rail ($y = Y_{bottom} = 0$).
     - `Input Terminals`: Nodes of `type: input` are placed on the left boundary ($x = X_{in}$).
     - `Output Terminals`: Nodes of `type: output` are placed on the right boundary ($x = X_{out}$).
   - **Phase 2: Stage Decomposition and Horizontal Sequencing**:
     - Identify all active devices (BJTs, MOSFETs).
     - Each active device defines a primary vertical column ($X_{stage_1}, X_{stage_2}, \dots$).
     - Order stages by traversing the signal path from input node to output node.
   - **Phase 3: Stage Geometry and Pin Routing**:
     - Center active device at $y = Y_{mid}$.
     - **Collector / Drain**: Route branches vertically UP toward $Y_{top}$ (collector resistors $R_C$, drain resistors $R_D$).
     - **Emitter / Source**: Route branches vertically DOWN toward $Y_{bottom}$ (emitter resistors $R_E$, source resistors $R_S$, and parallel bypass capacitors $C_E / C_S$).
     - **Base / Gate Biasing**: Place voltage divider branches ($R_1$ to rail, $R_2$ to ground) in an offset auxiliary column to the left of the active device.
     - **Inter-Stage and I/O Coupling**: Place coupling capacitors ($C_1, C_2, C_{\text{coupling}}$) horizontally between signal nodes.
     - **Output Load**: Place load components ($R_L, C_L$) at the final rightmost column ($X_{out}$).

3. **SchemDraw Component Mapping**:
   - Resistor $\to$ `schemdraw.elements.Resistor`
   - Capacitor $\to$ `schemdraw.elements.Capacitor`
   - BJT NPN $\to$ `schemdraw.elements.BjtNpn`
   - BJT PNP $\to$ `schemdraw.elements.BjtPnp`
   - MOSFET NMOS $\to$ `schemdraw.elements.NFet`
   - MOSFET PMOS $\to$ `schemdraw.elements.PFet`
   - Voltage Source $\to$ `schemdraw.elements.SourceV`
   - Ground $\to$ `schemdraw.elements.Ground`
   - Power Rail $\to$ `schemdraw.elements.Vdd`
   - Labels are formatted with component identifier and physical value (e.g. `RC\n2.2k`).

4. **CLI Entrypoint (`ceml render`)**:
   - `ceml render <circuit.ci> -o <output_file>`
   - Supports output file extensions `.png`, `.svg`, and `.pdf`.

## Consequences

- Endows CEML with native visual compilation from `.ci` markup to standard electrical schematics.
- Maintains strict electronic design conventions without requiring manual $(x, y)$ coordinates in `.ci` files.
- Provides immediate visual debugging and feedback during circuit specification.
- Allows downstream tools like `aicione` to consume `ceml.schematic` for visual overlay of solved analytical parameters.
