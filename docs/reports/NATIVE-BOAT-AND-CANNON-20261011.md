# Native Boat and Cannon contracts — 2026-10-11

Status: server-only Boat helper and actual World dispatcher integrated;13 pure/actual-dispatcher tests and5 isolated PostgreSQL tests through143 PASS. Original Java oracle PASS. Deployment and graphical round-trip acceptance remain pending.

## Original assets and protocol

The installed client's `bce.a(aKq)` creates `fzH` endpoints and registers all of them in `fzD`'s Boat registry, regardless of the endpoint's auxiliary kind byte. There are **87 endpoints**, and every endpoint joins one of the **87 physical Boat placements** by original identity and map. `clM/clN` are arrival XY, **clO is destination map**, and **clx is localization label ID**, not altitude. No arrival Z is present in this table.

The `bcd.a(aKr)` loader creates **393 original links**. Despite the two endpoint field names, these are **bidirectional**: `fzD.aQ(a,b)` explicitly matches either endpoint ordering. The original `bRc` menu likewise resolves the opposite endpoint. Neither all-to-all travel nor directed-only travel preserves this contract.

`bEu`'s ACTIVATE action invokes `bRm.b`, opening the existing local Boat menu. Selecting a destination invokes `bRm` → `csO13686`, containing two signed big-endian longs `(source_id, destination_id)`. No extra server menu or client change is required.

There are **301 unconditional links**, **3 exact real-level>=40 links**, and **89 links containing other criteria** (achievements, calendar windows, explicit False, or mixed conditions). Both original criterion strings must hold in either travel direction. The helper supports the first304 and rejects the89 pending authoritative evaluators. It does not waive restrictions or guess quest completion.

The original `aKr` has no kama or item payment fields. Its `aNI` descriptor is **animation**, not cost: `AnimLoading_Bateau`, transition duration2600/4800ms and fade600/800ms. This was confirmed through `bcb.a(aNI)` → `fzN` and the complete `fzI/bRm` route chain. No payment or reward is invented. The unused `aKr.clV` flag is retained in the inventory; the original loader does not consume it.

## Prepared API

`wakfu_server.native_boats.source(character, body)` identifies a current-map Boat source in13686; it returns None for other native transport kinds. `resolve(character, body, source_allowed=..., geometry=map_geometry)` validates an original matching eligible link and returns the existing native transport result shape, plus `native_link_id` and original animation metadata.

The caller's callback can use `admit_source(store, account_id, generation, character, origin, blocked=...)`. This checks the exact installed source definition, finite current coordinates, public instance, existing local interaction proximity (Manhattan<=4 and absolute Z<=1), selected session lease, owned row locks, durable combat exclusion, and full SQL/live source equality including level. Existing `STORE.transition_map` must then compare-and-set the same source before standard departure/bootstrap/join handling. Live occupation checks belong to the caller; the helper cannot infer crafting, trading, seats or other in-memory states.

Arrival altitude is accepted only when original destination XY has **one unique authoritative walkable edge-node Z**. Empty or multiple surfaces reject travel; no source altitude, label ID or guessed height is reused. A bounded read-only check against the currently published catalog found **78/87** unique arrivals; the following nine had no matching surface and remain rejected:

35193, 14697, 20243, 13146, 14695, 14696, 20959, 21019, 21036.

The check process exited; it did not write the public database or restart any service. Future geometry qualification should run sequentially with bounded per-map processes, following the current coordination memory policy.

## Cannon

The single physical Cannon is object16929, map189, position(45,448,22). It does not have a matching aKq endpoint or aKr link. Startup `aGZ.cfV` registers the ZAAP, DRAGO, Boat and HavenWorld transport providers, but no Cannon provider. A different endpoint35192 carries auxiliary kind3 in the Boat table; that does not establish a route for physical Cannon16929. Its destination and native executable interaction remain unproven. This worker neither enables a false cannon route nor modifies the client.

## Evidence and acceptance

- Full endpoint/link/criteria/animation ledger: [NATIVE-BOAT-CONTRACTS-20261011.json](NATIVE-BOAT-CONTRACTS-20261011.json).
- Runtime helper: `server/wakfu_server/maps/native_boats.py`; embedded deterministic dataset `native_boat_contracts.json.gz`.
- `PYTHONPATH=server python3 -m unittest discover -s server/tests -p test_native_boats.py -v`: **9/9 PASS**.
- Original Java oracle: all87 `bce` endpoints, all393 `bcd` links resolved in both directions, and exact csO13686 payload. Private evidence `.runtime/local/native-boat-audit-20261011/oracle.log`.
- Root must qualify actual dispatcher branches and session/ownership/combat/SQL rollback through isolated PostgreSQL before publication. Pure tests alone do not prove these transaction guards.

After coordinated deployment, use `/l !tp 504 4 3 9` outside combat and click the nearby original Boat18259. Its existing destination menu should include original Boat21678/map794. Select it: arrival must be(-3,-4,6) on map794. Repeat in reverse: native arrival is(4,2,9) on map504. Kamas and items must remain unchanged. Reconnect and verify the saved arrival. During combat, trading or another occupation, travel must reject without changing location. Unaccredited criteria and the nine empty-surface arrivals remain unavailable.
