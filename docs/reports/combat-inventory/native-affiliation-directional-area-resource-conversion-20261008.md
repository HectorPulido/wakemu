# Class-dependent native mechanisms 813, 1030 and 808

Bytecode source: installed `eYU`, `eYQ`, `eYV`, `eWq`, `eWr`, `aAS` and
`fff`. No class or spell ID supplies behavior.

## Directional area creation: 813/eYU

`eYU` inherits the native area runner, forces its keep flag true in `C`, then
calls ordinary area creation before updating the actual area's direction.
For a target adjacent in both X and Y it uses `aAS.cA(dx,dy)`; zero displacement
is native NONE (-1). Otherwise the direction is NORTH_EAST (7), including far
targets in other quadrants. Java subtraction wraps before this comparison.

The shared area handler and codec now accept the source-proven subclass. Initial
creation callbacks see the ordinary initial orientation; only afterward is
the registered area orientation and footprint updated. The original caster,
creator relation, cell, spell container and raw packet orientation are preserved.
The client executes the same derived runner after ordinary area construction.

## Temporary affiliation: 1030/eYV

`eYV` reads parameter 0 into its runner value. It cancels for amount -1, null
target or a target without the actual `amO` interface. Application saves the
current signed-byte `bcM`, narrows the amount to byte and calls `au(byte)`.
Removal restores that saved byte. It does not recalculate the most recent
remaining stack. The saved old byte is private calculation state, not fabricated
AdditionalDatas.

`NativeAffiliationHandler` is registered through shared factory preparation,
native runner events and retained stat removal. It changes
`native_fight_affiliation`, which existing native targeting and condition
providers read, while preserving the fight's immutable participant team and
ownership. Tests cover signed narrowing, stacked restoration and the actual
shared factory path. Syntax passed; single-agent automated validation is pending.

## AP as MP: 808/eWq

The mutable fresh-owned route is now registered; validation is pending.
`C` captures effective maximum AP. Application expands raw maximum MP by that
amount, adds current AP to current MP, registers an actual `eWr` listener on
the AP PA, and increments fight property 50 (`AP_AS_MP`).

Every PA notification compares current and maximum AP with the listener's
previous values. It first writes MP current plus AP current delta, then raw
maximum MP plus AP maximum delta. Maximum deltas accumulate independently in
the listener. Removal detaches that exact listener, subtracts the live runner
amount and accumulated maximum deltas from raw maximum MP, fills MP to its
effective maximum, then decrements property 50 and calls the base removal.

`combat_resource_pa_notifications` stores ordered, plain eWr listener snapshots
on the actual fight. Actual AP setter boundaries notify after scalar and PA
snapshots agree: normal/weapon/NPC cost debit, current-stat setters, AP loss and
removal, maximum families and removal, parameter-selected maximum, optional
eXO refill, native turn resource reset and `Fight.spend`. Maximum operations
notify even when unchanged; current operations notify only when current changes.
The eWN and eWO producers now preserve their separate maximum/minimum/current
notifications instead of collapsing their updates into one final snapshot.
Native eWh nonresource exclusions remain intact.

`NativeAPAsMPHandler` participates in fresh C/value events, shared preparation,
retention and ordinary stat removal. Listener records survive deepcopy and are
checkpoint-serializable. Removal uses the live retained runner amount and its
own accumulated maximum delta. Missing PA raw-current authority and unretained
listener ownership remain explicit unsupported routes; this is partial coverage,
not a claim that all native eWq reconstruction paths are implemented. Four focal
tests cover native setter ordering, old-MP-maximum clamping, preview isolation,
malformed authority, actual handler/property50 and removal. Syntax passes;
the sole validation agent owns execution of the queued regression snapshot.

The first mutable-only batch passed 38 tests, but subsequent source review
identified that AP and MP are expandable PCs. Passing that batch did not prove
the missing raw-current semantics. Original `fff.aYT` returns raw current;
`aYS` clamps it to effective bounds. A later original copied-pool export resolved
the separate `ffw.fZB` flag: `isExpandable` does not select `on`/`or` raw-current
behavior. HP has fZB=True, whereas AP and MP have fZB=False. Mutable AP/MP `on`
clamps to effective maximum and `or` clamps their existing raw current down;
frozen setters preserve raw current. The corrected producer keeps actual
fresh AP/MP setter operands, uses exact on/or/os/nG/oo operations, supports frozen
current with explicit raw authority, and sends raw current in native tB wire
snapshots. It never reconstructs hidden raw current from effective values after
effects. The fresh raw-current producer and original JVM eWq/eWr oracle remain
part of the next validation snapshot.

The structural graph contains one class808 definition: effect37098 belongs to
state702, with ancestor spell2038. Its actual eVy mode2 timing has duration-1,
growth0 and delay0, so this class route is retained at every level. The generic
unretained listener guard therefore does not remove this declared class route;
that generic variant remains unsupported rather than silently allocating an
unowned permanent listener. Structural reachability is not actual cast proof;
the class2038 conditional chain still requires runtime and manual acceptance.

Related shared maximum withdrawal correction: original `eWN.bbR` removes the
live raw applied amount from ordinary characteristic current, then removes it
from raw maximum. HP alone uses its saved effective maximum delta; when that
delta is strictly greater than current HP, subtraction is capped to current-1.
Equality still subtracts the full delta. Tests cover HP10/delta25 becoming1,
HP25/delta25 becoming0, and percentage-modified MP stacks withdrawing raw
amount instead of the saved effective delta. These regressions passed in the
38-test resource snapshot before the subsequent raw-current integration.

The AP_AS_MP casting policy is separate from the PA observer. Original `fcN.c`
rejects a positive spell AP cost when property50 is present; `fcH.a` reports
`twJ` for a positive weapon AP cost under that property. Neither path transfers
AP cost into MP. Original `fyF`/`fyQ` instead select explicit conditional cost
tables: actual spell2016 at level1 with state702 selects AP0/MP4/WP0. The shared
spell and weapon boundaries now enforce that policy before resource mutation.
Regression fixtures cover unchanged resources on rejection and the native MP
table, with actual player type evidence for its deck criterion. Full2038
transformation and subsequent spell transactions remain pending validation.
