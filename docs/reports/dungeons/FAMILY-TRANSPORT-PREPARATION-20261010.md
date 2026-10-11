# Native family transport preparation

Source-only preparation. No runtime activation or deployment was performed by this work. Nine of fifteen remaining ordinary transport/mixed cases have configurations with validated native terrain, six-player placement, directed encounter approach and a literal exterior exit. Boss mechanics are not certified. Composition and stage selection are explicit user-authorized local approximations.

Machine-readable evidence and configuration paths: `FAMILY-TRANSPORT-CANDIDATES-20261010.json`.

| Dungeon | Prepared stages | Policy / blocker |
|---|---:|---|
| Castillo de Wagnar | 3 | Exact `IsNeoServer()` alternatives excluded; classic `not IsNeoServer()` native endpoints preserved. |
| Pastos de los Jalatós | 3 | Same mutually exclusive classic/Neo filtering; no changed endpoint. |
| Hacienda de la Topera Oculta | 1 | Local family arena in the directed entry component. Optional internal transports have no reachable literal approaches in this component. |
| Mazmorra Milubo | 1 | Same entry-component arena policy; official stage count is not claimed. |
| Kokolost Island | 1 | Same entry-component arena policy. |
| Cono de Crújian Jerry | 1 | Same entry-component arena policy. The optional item-gated transport lies outside this arena. |
| Necrópelis de Morbax | 1 | Same entry-component arena policy. |
| Vid Vil | 3 | Local native transport spine. Both identified bosses, Sydonia and Copampino, occur once in the final encounter. Optional side branches are excluded. |
| Palacio Zollo | 2 | Local native transport spine; final victory followed by literal backward transport to the entry exterior exit. Optional side branches are excluded. |
| Factor Trool | blocked | Five reachable transport arrivals are missing from verified native exploration terrain: destinations 1169, 1170, 1172, 1173 and 1174. A family roster cannot establish walkability at those literal endpoints. No guessed arrivals were introduced. |
| Mazmorra Steamers | blocked | A spine and backward completion exit are provable, but native exterior object 33646 lies outside its selected rooms. Current object-state validation rejects that unbound exterior object. Needs explicit handling of excluded transport objects, or a topology covering all native exterior objects. |
| Astrolillo | blocked | Both native exterior exits lead to map 1211, whereas the route enters from map 235. The current exit contract requires the route exterior map. An explicit independently validated native return-map contract is needed; changing the entry map would corrupt entry identity. |
| Hacienda de la Balinería | blocked | Native transport 24175 leads from room 2 to an endpoint outside the physical room chain; return 24177 likewise has no source-room binding. Preserve exact endpoints and add the disconnected region to a supported combined topology. |
| Montaña Conohos | blocked | Native transport 35990 skips physical rooms 1 to 6; return 35991 goes 6 to 1. Existing transport runtime requires adjacent stages. Must gate the shortcut by final-stage unlock and support exact nonadjacent returns. |
| Escarantera Abandonada | blocked | Transport 24166 has no literal source approach within the physical room chain, despite arrival belonging to room 2. Need combined topology including its actual source component. |

## General safety rules

`prepare_family_transport_dungeons.py` never changes native destinations, client assets, combat geometry or spell handling. Local single arenas are allowed only when every omitted same-map transport has no literal approach in the selected entry cells. Reachable missing endpoints remain blockers.

The offline exit helper now prefers a dedicated non-entry completion exit and falls back to the room-one cancellation exit only when a fully literal, directed backward transport chain from the final encounter proves a completion path. Merely having an entry exit does not prove final-room reachability.

The native branch spine is an approximation of encounter staging, not an assertion about official dungeon room order. Unselected branch destinations fall outside the configured room mapping and cannot be used to bypass a configured stage. Native objects on omitted branches may remain visible; manual review should prioritize these layouts.

## Validation

`PYTHONPATH=server:server/tests .runtime/local/verification-venv/bin/python -m unittest test_family_transport_preparation test_physical_candidate_exits`: 12 tests passed. Coverage includes exact-only Neo exclusion, immutable source catalogs, refusal to erase reachable transport sources, no paid/cyclic local spine, dedicated-exit preference and literal backward-to-entry completion.

All nine candidates passed placement and directed sequence validators during read-only preparation. PostgreSQL lifecycle acceptance is a separate required gate before runtime activation.

## Manual priorities after activation

1. Vid Vil: verify both final bosses exist, no optional branch bypasses progression, and exit works after both die.
2. Palacio Zollo: win final encounter, use the native backward transport, then exit through the entrance object; verify a fresh entry creates a new run.
3. Wagnar and Jalatós: verify every classic transport route, three-character room movement and reentry. Neo alternatives must not be selectable as valid classic progression.
4. The five entry-component arenas: expect one local family encounter with its actual boss, not official multi-room progression. Check spawn reachability, group entry, win, exterior exit and fresh reentry.
