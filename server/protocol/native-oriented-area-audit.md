# Native oriented areas: anI, anG, anE and anJ

`combat_area_geometry.py` implements the client methods `anI.p`, `anG.p`,
`anc.a/b`, `amX`, `aBA.g`, `aBz.bp`, and `ana.n/o` inspected with Java22 javap.
`ProbeNativeOrientedAreas.java` is the reproducible native oracle; its output is
`native-oriented-area-fixture.json`.

anI emits the stem `(0,0)..(length,0)`, then alternating positive/negative
bar offsets at the stem end. anG emits x-major rectangle offsets; nonzero
even dimensions are rounded upward to odd dimensions. Squares are isotropic.
Directional shapes derive cardinal orientation from origin minus reference;
coincident points require the actor's explicit eight-direction facing.
The angle is rounded to float32 before the native quadrant thresholds.

Actor membership uses the transpose transform `ana.o`; cell enumeration uses
`ana.n`. For diagonal facing at coincident points these are not inverse
operations. The implementation preserves this observable client behavior.
Membership ignores Z. fcE membership dilates local raw offsets by the actor's
signed-byte physical radius; null-selector amQ membership does not use radius.

Selector origin/reference differs by path: fcE uses cast cell / caster position;
null selector uses caster position / cast cell. Group cell enumeration uses
cast cell / caster position and preserves native ordering before existing
terrain-height filtering.

Validation: the JAR probe passed 234 shape/orientation cases, each checking
enumeration and actor membership for radius 0, 1, and 2. The corresponding
Python oracle comparisons and targeting/group-cell regressions passed 22 tests.
The fixture includes diagonal self-facing and tests differing Z coordinates.

anE stores ordered signed XY pairs; its constant description `forme à base de
points` carries no coordinates. `ExportNativePointAreas.java` loads all aNw
definitions and exports 3,198 anE and 2,145 anJ entries into
`native-point-areas.json`. The runtime factory merges this compact metadata
after validating effect class, area class and native description. Original
catalogs are not mutated. The full spell/state exporter also writes these
points for future regenerations. Missing or conflicting metadata rejects.

anJ emits origin, alternating positive/negative bar offsets at x=0, then the
positive-x stem. Its native description is `t inv-barre:WIDTH-pied:LENGTH`.
Both anE and anJ use the same directional transforms as anI. The probe includes
negative coordinates, duplicate points and zero dimensions. Raw duplicates
remain in metadata; native cell iteration removes duplicates preserving order.
Tests validate all 5,343 compact entries and identity disagreement rejection.

Reproduce the compact export using Java22, compiling
`sniffer/java/ExportNativePointAreas.java` with `client/lib/*` and running it
from the project root with output path `server/protocol/native-point-areas.json`.
Reproduce the geometry fixture with `ProbeNativeOrientedAreas` and output path
`server/protocol/native-oriented-area-fixture.json`.

Scope: canonical anI/anG/anJ descriptions and exported anE points. Ordinary facing 0..7 is supported;
unknown/coincident facing and unknown fcE radius reject explicitly. This does
not establish geometry or physical-radius behavior for other area classes,
nor support native TOP/BOTTOM direction values as ordinary actor facing.
No spell identities or class-specific branches are used.
