# Shared forced displacement collision contract

Original targeted bytecode: eXD, eXK/eXJ/eXp/eXq, faz/fay/faw, eVI, eVZ, Qe and QI. No services or world state were touched.

## Detection and application order

faz computes the path, stopped surface, accepted step count and actual QK collider. eXD stores these before fPa. fPa does nothing when fOs is false or the actual resulting position equals fOu (desired endpoint). Otherwise a positive requested-minus-moved count sets AP-loss trigger rEa=1 and event trigger rDZ=true. eXK300 and eXJ301 have fOs=true; eXp331 and eXq305 have fOs=false. The latter two can truncate without collision AP loss or event204.

During eXD.c, L2 already occurred. When there is an actual destination, eXD applies physical movement first, sets running value to path.size, executes d, and then fPh before final orientation/application notification. If the destination is null, fPh runs on the bbs/server path before success marking. Existing handler emission/order must preserve this distinction; treating collision as an unsupported whole effect is not native behavior.

faz checks QI.R and physical B surface transition before occupancy. When displaced fax.bcP is true, QI.g(x,y,previousZ) determines obstruction; QI.V(XY) selects one registered QK. A PV different from the displaced object is retained as collider; a non-PV QK also stops the path but receives no AP/event PV callbacks. It uses actual QI registration and native iteration order, not HP or actor-center guesses. faS has an additional border-area blocker; that actor subtype is outside the current ordinary-radius0 contract.

QI.g first recognizes terrain flags256/512, then (unless biP override) scans complete QI.U registered obstacle IDs, tests QK.bcP and excludes temporarily unregistered IDs. QI.V resolves QI.T to actual biQ object. These producers must be shared with the general occupancy authority. Unknown registration/order must remain unknown.

## Collision losses and event204

fPh preserves this order:

1. If rDX AP-loss-enabled and rEa>0, call q(displaced PV), then q(actual collider) iff collider is PV.
2. If rDZ, deliver BitSet{204} to original caster channel30 and original displaced target channel3, both using original running effect.
3. If collider PV exists, create Qe.bbm clone, rebind its target to collider, deliver that **clone** to original caster channel30. Deliver the **original running effect** to collider channel3.

The last pair is intentionally asymmetric in original bytecode: private a(BitSet,PV) loads clone for caster delivery but loads `this` for collider delivery. Thus collider-local listeners see original source target/displaced identity and original UID, while caster listeners see collider target and fresh clone UID. The previous collision helper incorrectly used clone for both deliveries and requires correction before integration. No global replay channel is emitted by fPh.

q(PV) first checks actual PV.a(ffw.AP). Absent characteristic means skip. Otherwise eVZ.a(PN,AP,originalCaster,recipient) creates a fresh AP runner, eVI singleton supplies definition -13/action55 with requested1, ox2254 adds the explicit collision-loss event, g(recipient) executes and bal cleans up. The definition's PL is null. Native ordinary resource-loss guards, willpower float arithmetic and stochastic rounding, frozen/clamped AP, state5227 for positive actual loss, L1..L4 and callbacks all remain applicable. eVZ.C finally clamps calculated loss to [0,requested], so willpower alone cannot increase eVI requested1 beyond1. Any later value modifier would require its actual producer and explicit proof before expanding the codec contract.

The installed `collision-effect.json` already captures genuine eVI constructor metadata: no flags, no subscription, execution mode2, duration0, requested1. Extra runner event2254 is runtime state, not a definition event mask. Preserve that distinction in a shared lifecycle producer. Existing NativeResourceLossHandler provides calculations/preparation/application but its owned13497 codec accepts only positive generic references; collision has a verified12613 synthetic-13 codec. It needs an explicit native synthetic delivery policy, not a global packet-family change.

## Integration boundaries

General integration requires: exact path collider provenance; a synthetic resource runner with actual eVI metadata and null PL; signed source identity/zone/timing/event-cost producers; shared resource lifecycle and mandatory state5227 executor; direct local event204 replay with the asymmetric clone pair above; fresh UID order. Geometry must mutate before nested loss/reaction events so criteria observe the native position. All actions belong to the same private checkpoint/transaction; any unresolved dependency rolls back, rather than silently skipping AP or events. No spell/class IDs select behavior.

## Scoped fixes completed

The collision helper now preserves original UID/target for collider channel3 and uses the fresh target-rebound clone only for caster channel30. Regression tests cover exact recipient/channel/target/UID sequence and clone allocation only after the original pair replays. The geometry producer now records fOs-equivalent collision_reactions independently of loss_ap; eXp331 truncates the existing verified/explicit legacy path without AP/event204, just like eXq305. Original runner probe verifies all four fOs values without loading catalogs. These fixes do not connect incomplete synthetic AP execution or invent QI registration. Five pure tests pass; broader integrated validation is delegated.

## Shared geometry-to-executor connection

The ordinary displacement handler now consumes actual serialized QI.R before surface transition, the complete registered QK population for QI.g, terrain masks256/512, movement override biP and ignored IDs biN. It respects the displaced QK's actual bcP. When obstruction occurs, QI.V is resolved independently of whichever obstacle made QI.g true: a singleton QL membership can select an actual registered actor even if that actor is nonblocking and the obstruction came from terrain. Multiple memberships still reject because the checkpoint does not preserve the actual TByteHashSet insertion/deletion topology. A registered faW/Qq collision also rejects until its PV resource/Qf callback producers close.

A verified push/pull collision now truncates and invokes the configured shared collision executor with the original running UID, actual path size, displaced actor and actual singleton collider. Physical coordinates and QI registration are updated before nested AP loss and event204 execution. Families331/305 retain fOs=false and truncate without that executor. Missing geometry or executor authority still rejects before coordinate mutation; no class/spell ID chooses behavior.

Six new pure geometry tests and six selected-surface tests pass together: `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_displacement_qi_collision test_combat_teleport_surface -q`. They verify actual singleton actor selection, temporary ignore behavior, unfiltered QI.V selection despite a terrain blocker, multi-slot rejection, moved coordinates/registration before reaction and L3, and nonreactive331/305. The collision callback is observed here; separate resource tests establish its calculations/codec. Complete integrated replay remains a separate verification requirement.

Lifecycle ordering must be assessed per family. Original eXD.c itself invokes fOZ at offset44, which computes forced path/collider and fPa after L2; its C computes requested direction/parameters. Thus moving every displacement path calculation before L2 would be incorrect. Original eZB.C performs selected-surface/property acceptance before L2, and that family still needs a separately prepared acceptance-state lifecycle to move those checks to their exact calculation phase. This checkpoint does not claim that remaining lifecycle gap is closed.
