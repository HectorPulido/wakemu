# Cell group raw definition identity in compiled catalogs

The ready-turn family349 failure for reference384594 was a collection
representation mismatch. The original metadata exists and specifies `anH`,
raw parameters `[1,0,0,0,1,0]`, and a present native criterion. Ordinary group
population receives that raw definition separately from evaluated level values.

`CompiledEffects` uses `ImmutableCatalog`, which freezes the raw JSON parameter
list into a tuple. The previous identity guard compared the metadata list with
the frozen tuple directly and rejected identical values. The shared guard now
compares supported raw sequences by exact ordered elements. It still requires
matching area class and native criterion presence, and rejects changed raw
parameters. It does not substitute evaluated parameters or invent metadata.

A regression constructs an actual `CompiledEffects` view using the published
reference384594 raw metadata, confirms the tuple representation, and checks
both raw and compiled definitions plus corrupted parameters/area class.
Seven cell-group tests passed; the combined cell-group/captured-codec/selected
creature suite passed13 tests. Live ready-turn validation is delegated to the
coordinated offline auditor. No services or world process were restarted.

## Per-cell criterion recipient bridge

The subsequent actual turn-start run reached the criterion and exposed a
second shared gap: family349 sends an actual cell argument, but its invocation
carried only a null PV target with no cell-argument attestation. The condition
adapter correctly refused to treat that as a completed empty QI lookup.

`EffectInvocation` now has an explicit raw-cell argument marker. Family349 sets
it for candidate criterion evaluation. Before building condition aliases, the
adapter resolves the first actual native fighter through authoritative ordered
QI occupancy. It preserves the raw XYZ argument independently from that actor
alias and retains the original trigger, container, level and running context.
Occupied cells select their actual actor; known empty cells select null;
missing registry topology remains unknown.

Two fresh-QI regressions exercise occupied, empty and unknown cells and verify
source-context preservation. The focused bridge/cell-group/UseGate suite passed
31 tests. The coordinated actual class3 turn-start re-audit remains the next
runtime validation boundary.
