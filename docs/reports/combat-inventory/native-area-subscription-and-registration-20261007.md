# Native area subscriptions and registration geometry

## Default production producer

The source-proved callback producer now defaults on in the effect factory,
atomic area boundary helpers and the five normal game-server entry gates.
Explicit `WAKFU_NATIVE_AREA_CALLBACKS=0` still requests the legacy disabled
policy; unsupported prototypes, shapes and event producers still reject.
The Ready05 Feca1474/1475/1476 failures came from the disabled producer,
not missing radius1 cross geometry. The Feca integration regression now
removes the opt-in override and exercises creation and native turn-start
delivery through the default policy.

No live environment or service was changed. The AI bridge remains outside
this change: its absent-variable default still supplies
`native_area_callbacks=False`, and NativeOracle consequently skips its own
turn-start and path-step area callbacks. Normal game-server defaults alone
do not establish parity for those AI-owned boundaries.

## Shared subscription contract

The original Qq stores arbitrary nonnegative native BitSet indices in its entry and exit masks. `Qq.a(BitSet,Qe,amP)` intersects those masks and runs entry before exit. `faV` then intersects its independent removal mask. Registration does not produce an activation event.

The previous server rejected a prototype at creation whenever its subscriptions included an event outside the local external-event producer list. That rejected valid installed10016 subscriptions, including glyphs and auras. `NativeAreaEventRuntime._definition` now validates the installed BitSet domain without claiming an external producer for every subscription. The external `event()` entry point still rejects unimplemented producers; an actual running source can supply its verified native event bits.

The actual native probe `ProbeNativeAreaCallbacks` passes entry, exit, irrelevant, combined and10016 routing. A scan of original client bytecode found no literal10016 producer. Consequently this change preserves and delivers10016 from an actual Qe source; it does not infer10016 from a turn, creation, movement or area presence. The unavailable original server producer remains a proof gap.

## Generic PV delivery

`Qq.a(BitSet,Qe,byte)` forwards to its actual nullable Qf first, then routes its own callbacks only on `bcx()==1`. The shared ordinary lifecycle now performs that ordering through the registered area runtime. Null Qf skips listener replay while retaining the actual Qq callback. An enabled callback receives the existing verified NativeEventSource, including source UID, original target, event bits and trigger identifiers. The actual area object is captured before Qf reactions, so unregistering its spatial record does not substitute a different object.

The eXE current-stat area path uses the same lifecycle when available, instead of separately invoking the own callback and omitting Qf/global delivery. Legacy direct callback consumers continue rejecting unproved Qf subscriber delivery. The general phase requires callback authority when a matching subscription exists; it does not silently drop that subscription.

## Actual shape data and orientation

`anE.bEm()` omits the point list. The installed Qq exporter now includes actual ordered `bcD().bEl()` points for anE and anJ. The catalog contains95 such prototypes. The registered-area geometry adapter forwards these points into the existing native shape engine; it previously forwarded only class and description.

Original `Qq.bcT` enumerates its shape using the actual creation position and `bcU/bcV/bcW`, which resolve the actual owner coordinates when an owner exists. The geometry reference is therefore not always the creation cell. The creator now captures that reference at registration and projects the shape with it. A fixed glyph keeps its cached footprint after owner movement. The separate faN owner-following query refresh remains distinct.

`ProbeNativeRegisteredAreaGeometry` passes an actual Qq.bcT case with asymmetric ordered points, creation cell(5,2), owner(0,0), and facing7. The native cached cells are(6,2) and(5,3), independently of Z. This would differ from the former forced-coincident facing projection.

`anw.bEj()` returns true: cardinal cross arms stay in world XY, including
unequal lengths. Their h/b/g/d rays point respectively +X/-X/-Y/+Y; a
negative arm has no positive-index cells and does not remove the center.
The former asymmetric-cross rotation rejection was therefore incorrect.
`ProbeNativeRegisteredCrossGeometry` records 288 actual Qq.bcT cases across
scalar/two/four arm parameters, all eight directions, translated centers
and three owner references. The server differential regression consumes
that native oracle directly.

## Movement lists and reactions

Original `Qs.a(from,to,PV)` first constructs all three actual-object lists through `bhs.forEachValue`, then delivers entry10001, internal10008 and exit10002. Prior membership uses `Qq.d(from)` on the actual center; destination membership uses `Qq.a(PV,to)` and its signed-byte physical footprint. It does not rescan registered areas between callback phases.

The server now consumes the explicit native Qs map topology for registered-area iteration and freezes those three lists before reactions. A callback that unregisters a later area cannot erase its already scheduled delivery. Destination footprint checks preserve the native center-first rule, including negative-radius behavior. Missing legacy topology keeps the older bounded iteration domain; it is not evidence of native order.

## Verification and limits

New tests cover native subscription versus external producer distinction, malformed indices, actual10016 running-source identity, Qf-before-Qq order, null-Qf own callbacks, channel selection, actual owner geometry reference, consumption of all95 installed point-shape metadata records, native map delivery order, frozen object delivery after unregistering reactions, and actual destination footprint. Automated Python execution is delegated to the shared validation worker. Both native Java probes pass. No services were restarted.

This closes general rejection and projection mechanisms. It does not certify every class, recover external area event10006 or10016 causes, implement unregistered area subtypes, or establish client visual acceptance. DEPOSIT and WALL remain separate native subtype contracts.
