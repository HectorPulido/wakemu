# Sliptorium: native backward final exit

The previous direct-final-room-exit requirement was too restrictive. The literal native route is:

1. Finish the encounter in native room 3 (map 325).
2. Walk from the final-room anchor (144,-59,0) to source 16126 at (144,-53,0): seven directed native path cells.
3. Use native destination 900, arriving in room 2 at (203,93,0).
4. Walk ten directed native path cells to exterior source 14012 at (210,91,2).
5. Use native destination 692 to map 323 at (0,-131,0).

No endpoints, map heights, or transport criteria were replaced. The complete path witnesses are in `SLIPTORIUM-BACKWARD-EXIT-CANDIDATE.json`. The offline builder now accepts a unique non-entry exterior reachable through literal adjacent backward links, checking the native destination and source approach, unconditional/free travel, and directed walking paths within each room. Entry cancellation still requires exactly one native room-1 exit.

An additional source incompatibility was found: `server/wakfu_server/maps/dungeon_object_states.py` rejected every exterior in an intermediate room. The source change allows only the explicitly bound exterior named by `completed_exit_witness`, and publishes it usable only after completed progress. Unproved intermediate exits remain rejected. Backward travel and server-side exterior authorization already support this operation.

## Deployment blocker

This candidate is **not activated**. The running world still has the older object-state module and would reject hydration. Read-only hash inspection found:

- Running `/app/wakfu_server/maps/dungeon_object_states.py`: `54b410582f1a175e5f00d9f15e1efa9652458d55dc34c26eaba6df6f94b65385`.
- Updated local source: `aa061847b831c292a0520a5d2784374569008f812a87ec4ba62826b38bcba725`.

A complete current-checkout image build and deployment is required before activation; do not overlay this module onto an old image. No runtime rows or services were changed by this work.

## Validation and content limits

`test_physical_candidate_exits` and `test_dungeon_object_states`: **15/15 pass**. Regressions cover the literal backward proof, changed arrivals, criterion-gated travel, invented approaches, unreachable source, completed-only intermediate exit visibility, and missing/mismatched witness rejection. A dedicated isolated PostgreSQL lifecycle test passed (1/1): real native room transitions, completed-only visibility of exit 14012, actual backward transport 16126/900, and exterior return 14012/692 to map 323. [Audit](SLIPTORIUM-PG-LIFECYCLE-ECONOMY-20261010.json) binds test/source/config hashes and records `runtime_activated=false`; this is source validation, not live activation.

The guide has two encounters while the native topology has three regions. The candidate explicitly retains a nonofficial local three-encounter adaptation and exactly one Nonne (reference 1786) in the final encounter. Boss mechanics remain unverified.

Rebuild the offline candidate with the configured read-only native catalog connection:

```sh
PYTHONPATH=server .runtime/local/verification-venv/bin/python server/tools/prepare_sliptorium_candidate.py
```
