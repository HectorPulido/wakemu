# Dungeon run identity and native asset map identity

The current server already keeps these identities separate: `characters.map_id`
selects the native environment, while `characters.instance_id` scopes private
server state. `maps/native_transports.py::bootstrap` writes `map_id`, not
`instance_id`, into the format-28 POSITION world ID in message 13974.
`dungeon_instances.py` likewise stores the destination map and private run ID
in separate character and transition-outbox columns. Do not replace this existing
separation with bit masking or encode a database run ID in the asset map field.

## Installed-client evidence

Disassembly of the installed `client/lib/wakfu-client.jar` shows:

- The `csW` handler reads POSITION into `big`, obtains `big.arM()`, associates
  `ProtoDungeon` with that world ID using `ceG.b(long,eUZ)`, and calls `nl(long)`.
- The ordinary branch of `nl(long)` calls `Wc.a(long,Wa.bnj())`.
- `Wc.a(long,Wb)` passes the same long unchanged to `Wb.ft(long)`.
- `Wa.ft(long)` calls `Wa.a(long,ZT)`; that method passes the same value to both
  `Vg.b(String,long)` map-coordinate loaders.
- `Vg.b(String,long)` supplies the full `Long` to `String.format` before reading
  the asset through `aoM.bD`. No masking or truncation appears in this path.
- The alternative `ceK.nc(long)` branch is **ranch initialization**. It requires
  ranch server data (`fBE`) and a registered biome (`fBo.vp(long)`). It is not a
  general dungeon run-to-asset mapping mechanism.

Private disassembly artifacts are under `.runtime/local/dungeon-asset-*.javap`;
the existing handler evidence is `.runtime/local/unknown-world-handlers.txt`
(13974 handler offsets 1242–1377; `nl(long)` ordinary/ranch branches).

## Regression check and remaining integration

`server/tests/test_dungeon_asset_identity.py` proves that two different large
private run IDs yield the same native bootstrap when their asset map is 1086,
and that changing the asset map to 1459 changes the wire world ID independently.
Both pure tests pass. No runtime or combat code was modified.

This does not certify complete dungeon hydration: a transition consumer still
needs an authoritative per-run context, instance-scoped actor/static-state
publication, map-ready replay, and visibility isolation. The protocol evidence
supports server-private run identity plus native asset-map world ID; it does
not establish an additional native field for a database run ID.

## Native teleporter approach cells

`bEG.dST` decodes the object's `bbx` short through `QV.aa`, rotates relative
flags by `bcy().dyI`, and applies `aAS.wL(...).dyJ/dyK`. Non-center cells use
`VF.v` to select terrain altitude; this calls `VA.a` with the mover settings
from `VF.a(6, 0, 4)`. `ExportNativeTeleporterApproach.java` reproduces this
static selection using the native `VB` surfaces and `VA` implementation.
Dynamic occupied-cell restrictions remain runtime concerns.

The Jalato entrance object 26842 on asset map 527 has mask 1 and orientation
3. Its sole native approach is (-245, -89, 0), while its raw object position
is (-245, -90, 2). Requiring the raw position makes the gate inaccessible.
The catalog now records exact approach positions for every supported source.

The six static teleporter objects on map 1086 have mask zero. `QV.aa(0)` is
empty, and `bEk.dSw` returns an empty action array when `aWu` is empty.
Therefore their static payload alone does not establish accessible native
menus. `bEH` loads the mask from base-state offset 17 (a short); `bEI` dynamic
state updates modify usability, visibility and flags but do not set that mask.
No inferred neighbor or invented mask should replace missing native authority.

## Official victory capture resolves the zero-mask door contract

The October 8 official first-room capture proves that zero-mask doors do not
need a context menu or an invented approach mask. Object 26845 initially has
visibility and usability disabled. At victory the server sends two 12344
updates: visible with usability disabled, then visible and usable. Applying
both captured blobs to objects in the local and official JARs leaves mask zero
and produces the same state changes. The partial field 2 blobs are:

- Reveal: `01020000000602000101000000000000000000`
- Enable: `01020000000602000101010000000000000000`

The server then sends 13530 directed movement for the player's actor to the
exact source cell (0, -27, 0), with direction 7 and movement mode -1. This is
interruptible client movement: the capture includes replacement paths before
the player crosses later. Crossing emits native 12296 with source 26845,
destination 2506, flag 0 and mode 2. Backtracking emits the same message using
source 26849 and destination 2509; exiting uses source 26843 and destination
2505. The native topology independently verifies that all six map 1086 source
cells are walkable.

Room entry snapshots use 13984 to hydrate current static object states. Room 1
has its exterior exit available and its forward door hidden/disabled; room 2
has its reverse doorway available and its forward doorway hidden/disabled.
The general `dungeon_object_states` helper encodes final hydration snapshots
from the committed room frontier and emits reveal-then-enable deltas after a
victory. It preserves native identities and masks; dispatcher authorization
and durable progression remain separate responsibilities.

Private evidence: `.runtime/official-dungeon-capture/door-transition-evidence.json`.
