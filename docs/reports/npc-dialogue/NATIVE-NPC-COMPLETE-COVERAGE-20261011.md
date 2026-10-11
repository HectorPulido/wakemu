# Native NPC coverage and original initial scenes

## Complete speaker inventory

The installed native dialogue catalog contains 422 conversational speaker breeds.
`sniffer/export_native_npc_coverage.py` inventories every one, preserving original
capture positions, observed dialogue openings, and inferred quest-marker candidates
as separate evidence. It checks original server provenance and deduplicates capture
hashes. Private output: `.runtime/local/native-npc-complete-coverage.json`.

| Evidence before objective-criteria qualification | Speakers |
| --- | ---: |
| Unconditional observed initial contract | 1 |
| Observed conditional dialogue | 3 |
| Original position without initial dialogue binding | 5 |
| Quest-marker candidate only | 125 |
| Dialogue catalog only | 288 |
| Total | 422 |

Nine conversational breeds have ten distinct original captured positions. The
454 creation-capture actor position records and 227 dungeon-capture position
records include monsters, repeated actors and movement; they are not 681 distinct
conversational NPCs. Before the protector-identity recovery below, Wuan, Magnum,
B. Tóven, Mod'Ulo and Otomai had original positions without accredited initial
dialogue bindings. Otomai is now qualified separately by migration142. No root is inferred from
portrait, name, action number or proximity alone.

The independent full Lua scan finds 27,263 scripts, 1,578 actor-creation calls,
and 1,143 literal XYZ records in 196 scripts. These are visual/cinematic actor
coordinates; without map/breed/initial-root joins they do not authorize world
spawns. See [the source ledger](NATIVE-LUA-ACTOR-SOURCE-LEDGER-20261011.md).

The original POI loader independently decoded all 720 map files without errors:
1,887 markers and 2,597 interactive payloads. Native marker types and category35
label IDs do not encode NPC breeds; their consumers do not establish additional
NPC/position/initial-root joins. See [the POI schema audit](NATIVE-MAP-POI-SCHEMA-20261011.md).

## Definition-backed initial scene extension

Migration 139 adds an empty, ownership-bound NPC objective-facts table. Its
definition catalog contains all 6,029 native objective IDs. The native manager
initializes known objectives incomplete; unknown IDs throw. The server supports
only verified objective completion checks, their negation, conjunctions, and
`GetInstanceId() == N`, where the latter reads the published POSITION world
identity (`map_id`), never the SQL private-instance ID. Unsupported criteria
remain unavailable. No quest rewards or progression are implemented here.
The active catalog's 21-byte ACHIEVEMENTS default was also consumed completely
by the installed native envelope/facts parser, confirming empty completion
facts and incomplete states for all three relevant objectives.

Three additional source-grounded local initial scenes are prepared:

| Speaker | Native actor | Map and original XYZ | Native action → initial root |
| --- | --- | --- | --- |
| Huly5461 | -1706442046308322 | 1385 / (-17,-4,17) | 1243 → 5765 |
| Kheperalia5467 | -1706442046308328 | 1385 / (12,32,1) | 1255 → 5782 |
| Airyna5460 | -1706442046308339 | 1388 / (0,-19,3) | 1390 → 5755 |

These join exact preceding original actor spawns to outgoing13222 and incoming
12969 with identical actor identity. All use original creation source SHA256
`eedbfd7561e0ae53398bab0eddd26bfac674fb77953d537cea4dbbecd9c4cd69`.
Like Grugal in migration 132, publication is an explicitly authorized local
initial-scene adaptation. Original quest visibility and later actor movement
remain unimplemented. Initial choices only close; no inferred tree edges.

Independent read-only geometry verification confirms all three original XYZ
locations are exact published walkable cells: map1385 has 2,317 cells and map1388
has 339. No height or neighboring coordinate was synthesized.

Conditional opening requires the production owned-facts callback. The current
character's scene remains authoritative while facts are loaded; SQL exterior
coordinates are not reloaded. Facts and action/root criteria are reevaluated
on every choice. Foreign ownership, unsupported facts, private-instance scene
mismatch, stale placement and out-of-range interaction reject.

## Manual acceptance after complete deployment

Independent Luna gate:31/31 focused tests passed, including three isolated
PostgreSQL cases on the contiguous migration1–139 snapshot. NPC-owned source,
catalog, migration and test hashes remained stable. The shared dispatcher
changed concurrently only for root's unrelated intergame shutdown guard; no
whole-dispatcher stability claim is made. Receipts are under
`.runtime/local/verification-fast-20261011/npc140/` (directory keeps the old
reservation name). The production owned-facts callback was exercised from its
actual AST without loading services.

Use the existing server chat teleport command, then approach and click each NPC:

1. `!tp 1385 -17 -4 17`: Huly must appear at that captured location and open root 5765.
2. `!tp 1385 12 32 1`: Kheperalia must appear and open root 5782.
3. `!tp 1388 0 -19 3`: Airyna must appear and open root 5755.
4. Close and reopen each initial conversation. No quest item, reward or automatic
   progression should occur. Move away and confirm opening is rejected.
5. Reconnect and confirm the NPCs remain confined to their correct maps. Existing
   Grugal at map 1387(-12,0,2) remains available. The four quarantined map 1134 trial
   actors must remain absent.

These commands target exact original walkable actor cells; graphical teleport
behavior requires the deployment acceptance gate.
The overall request to place all native NPCs remains open: four prepared initial
scenes do not cover all 422 speakers or reconstruct original world visibility.

## Additional original identity recovered after migration139 qualification

Otomaï5459 at original map1385 `(20,17,1)` opens root5772 through native action1244,
but its dialogue speaker is PROTECTOR424 rather than the clicked actor ID.
The original13974 protector records directly bind424 to actor
`-1706442046308330`, and the installed client resolves this exact actor link.
This is an accredited fifth initial binding, still offline and outside the
stable migration139 publication. It must not be enabled by accepting arbitrary
speaker mismatches. See [the native identity proof](NATIVE-OTOMAI-PROTECTOR-ACTOR-JOIN-20261011.md).

Native minimal publication has independently passed using only protector
identity, its territory93601, appearance22193 and exact actor link. The installed
world library proves territory93601 belongs to map1385. No captured ecology,
weather or economy state is required. Implementation requires a separately
qualified speaker-identity contract and protector registration before opening.

## Additive protector speaker implementation142

The exact fifth captured binding is now implemented offline in additive
`142_captured_npc_protector_identity.sql`. Otomai5459 remains at native
map1385 `(20,17,1)`, direction3, public instance0; action1244 opens root5772
with original wire speaker type1 / protector424. Native definition criteria
require map1385 and incomplete objective10596, evaluated against owned facts.
Only choice13288 closes the initial scene; no quest progress is inferred.

The native protector record retains territory93601, appearance22193 and the
exact captured actor link. Its41-byte layout matches the installed original
serializer. Bootstrap publishes that record only when the exact qualified
placement is enabled; unrelated maps/private instances publish no extra
protector and perform no protector database query. Missing/contradictory joins
fail closed; a generic NPCspeaker2 substitution is rejected.

The root owns native13974 bootstrap and native12535 speaker resolution hooks.
Independent helper/dialogue qualification passed32/32 pure tests; the native
Java record/manager/registry/list oracle passed with exact byte equality.
PostgreSQL qualification passed6/6 against current migrations1–142, with exact
source snapshot hashes and successful isolated-schema cleanup. The root
separately qualified bootstrap/dispatcher integration; no deployed claim is
implied by those tests.
This still does not recover every native NPC or the full quest dialogue graph.
