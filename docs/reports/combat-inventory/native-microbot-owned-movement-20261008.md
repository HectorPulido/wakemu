# Native Microbot owned movement

The installed client separates rail construction (`fdp`/`fdq`/`fdl`) from owned requested movement (`byT`/`byU`) and MP display/accounting (`dbe.a(byR)`). Existing native network geometry differential covers 100 trials and 1,925 points; it did not certify gameplay movement.

## Recovered native contract

- `fcb.fg(byte)` iterates `bL(team)`, resolves each original actor's owner network and excludes networks whose segment list is empty. `fdZ.a(eGj,fdy)` checks the actual team byte only. It does not filter by HP or require the moving actor to own the network.
- `byT.a(big,beS,int)` delegates ordinary movement immediately when MP is nonpositive or `frx()` is nonnull (carried). Otherwise both origin and selected destination must belong to a same-team rail network.
- `byU.a(...)` rejects an edge when its destination is outside that rail membership or the inherited movement path test rejects it. The owned server consumer takes an already requested and FSM-validated path; it does not reproduce mouse projection or generate A* alternatives.
- A usable rail path requires length at most `MP * 3`, with native int arithmetic. Property `ffe.sfo`, numeric **98**, permits the special always-one-MP path branch.
- `dbe.a(byR)` computes rail MP as `(length + 3 - 1) / 3`, or **1** with property 98. Ordinary requested-path length remains its original cost.
- Property `ffe.seU`, numeric **77**, rejects fallback off-rail movement. Carried/nonpositive-MP delegation occurs before this property check.
- `amK.bDT()` returns its actual path-array length. The server request decoder already provides destinations without the initial actor cell.

## Implementation and verification boundary

`combat_rail_movement.movement_cost` consumes actual current carry/PB authority and persisted native network membership. `Fight._move_actor` preserves coordinate, occupancy, walkability, altitude/edge and MP validation, then uses this cost. It does not manufacture a walkable rail edge, overwrite resources or reconstruct a missing owner network. Normal fights without a runtime/network provider retain their existing movement contract.

`server_runtime` installs the existing registered actor authority through the runtime factory on Ready, casting and turn previews. Durable checkpoint and transient source comparisons exclude that runtime callback; restored objects need the actual factory to rebind it. Durable production checkpoint recovery aborts interrupted fights rather than resuming an active timeline.

Nine focused regressions verify ceil-three-cell cost, property 98, same-team sharing, altitude identity, property 77, carried fallback, retirement, missing authority and checkpoint omission/rebinding, and actual FSM/animation/stats debit for three-, four- and six-cell paths. Actual gameplay evidence is intentionally separate: `audit_microbot_rail_lifecycle.py` uses production Ready, the actual granted Microbot UID, normal owned casts, decoded client movement with area callbacks, production turn boundaries and recasting. Its serial execution is delegated to the validation agent; this document does not claim that execution passed before the report exists.

## Actual owned transaction checkpoint

`microbot-rail-lifecycle-01.json` SHA256 `d4a15f05babfc8f5a68c76993f06fe1e055f9a3a20c34cd96292aa5c37b4981a` has stable sources and verifies map1134, Steamer200, deck Maquinaria6919 and the actual Ready grant Microbot7008:

1. From `(-8,-7,-1)`, Microbot at `(-7,-7,-1)` commits for1AP+1WP, producing area222/prototype978.
2. After actual end/ACK/start, Microbot at `(-5,-7,-1)` commits for1AP+1WP, producing area227. The actual link covers `(-7,-7,-1)`, `(-6,-7,-1)`, `(-5,-7,-1)`.
3. Entering the rail from the outside origin costs1MP for one cell. Moving from the first bot through the middle cell to the second costs1MP for two cells, with actual `on_rails=true` movement evidence.
4. The requested three-cell return leaves the rail and fails for insufficient MP. This is not evidence of a longer all-rail path. Three-/four-/six-cell debit is separately covered by FSM unit regressions.
5. Eight production end/ACK/start cycles retain both bots. They do not demonstrate timer expiration.
6. A normal Microbot cast on the first existing bot removes area222 and the segment; area227 remains. This is actual removal, not a new constructor or reuse. The follow-up tool now requests a second normal cast to prove reconstruction with a fresh UID; that follow-up remains pending until its report is produced.

Prototype978 has `native_obstacle_id=-1`, source `fbm.constructor`: it creates no spatial obstacle slot. Membership reuse must therefore be distinguished from obstacle-slot allocation/reuse. The old report's empty retired trace used an incorrect observation attribute; the revised tool records the actual `native_retired_area_managers` field without changing gameplay.
