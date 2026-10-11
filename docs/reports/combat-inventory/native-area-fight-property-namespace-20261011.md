# Native area fight-property namespace — 2026-10-11

The actual Xelor7189 dial branch reaches314340, `not HasFightProperty("target",11)`, with target254, caster7 and cell(-5,-7,-1). Its outer313309 and313218 exceptions are propagation frames, not evidence that the failing predicate received a null target. The adapter currently builds registered-area ConditionActor aliases without fight-property authority, causing `Missing native PV fight properties`.

Original eMo narrows the requested ID to byte, resolves `ffe.Ua`, then calls `PV.a(PE)`. Original faV implements this as exact object membership in its rzt set. Its integer property loader `M(int...)` resolves fbo.Tn, a different enum namespace. Its typed setter `a(PE,byte)` accepts only PE namespace4; ffe uses namespace1. Thus fbo11 is not ffe11. The complete validated area-property list must never be copied numerically into fighter property IDs.

`sniffer/java/ProbeNativeAreaFightPropertyNamespace.java` instantiates an original faZ-derived hour, fills all15 fbo properties and checks all120 ffe properties. Every ffe membership is false, including after attempts through the original typed setter. All actual fbo memberships remain true. The offline probe passed. It requires no game service, database or catalog load.

```sh
javac -proc:none -cp 'client/lib/*' -d /tmp/wakemu-area-property-namespace sniffer/java/ProbeNativeAreaFightPropertyNamespace.java
java -Xmx128m -cp '/tmp/wakemu-area-property-namespace:client/lib/*' ProbeNativeAreaFightPropertyNamespace
```

Proposed repair: expose the verified area's separate fight-property authority only after its actual constructor contract and complete current fbo set/provenance validate. The current registered-area resolver already validates that complete set. A missing or malformed area producer must still reject; no unconditional empty fallback is justified. The concrete adapter/producer change is awaiting parent review. This proposal is independent of spell/class IDs and preserves actual null-PV behavior.

The parent approved and the narrow repair is now implemented: `registered_area_pv` exposes the separate empty ffe membership only after its existing constructor identity, full current fbo properties and provenance validate. The adapter uses this verified field for area ConditionActor aliases, including actual null-Qf areas. Unknown/malformed producers still reject. Generic namespace/provenance regressions and the real7189 casting regression are queued; implementation is not yet accepted by those tests.

## Next recipient boundary exposed by the fix

The repaired predicate advanced; the actual subsequent error was `Swap requires native actor target` at314357, not a repeated missing-property error. The failing selected area was1551/faZ, native concrete classbcU. Original bcU inherits Qq.b(IIS), which throws an unsupported-area-teleport exception; inventing movement for that area is unjustified.

Original parent313309 intentionally selects an owned area. Its child314340 has fcE mask `1 | (1 << 50)`, not plain1. Original fcE at bytecode offsets918–942 explicitly requires the candidate QK.bcN byte to be nonnegative for bit50. The hour's actual slot is−1; the colocated registered fighter has an indexed slot. The fresh server relationship-selection policy omitted bit50 and retained the parent's explicit area PV, bypassing the child's required selection. The parent approved adding only bit50 to the existing explicit fresh-child reconstruction policy. Native chosen-PV/event replay remains unchanged. No spell/class IDs, plain-mask1 exception or fake area swap is introduced.

The narrow extension is implemented with generic positive, no-recipient and unknown-slot-authority regressions. Actual7189 replay through normal casting is queued. Native eYg's default target transmission remains unchanged; this repair is the named fresh-server selection policy, not a claim that original native replay reselects its already chosen PV.

## Native hour-layout qualification, October 11

The remaining 7189 failure was an incorrect fixture expectation that both layouts must create twelve hours on the same terrain. The actual exported anE points under 313199 are `(2,1),(1,2),(0,3),(-1,2),(-2,1),(-3,0),(-2,-1),(-1,-2),(0,-3),(1,-2),(2,-1),(3,0)`. Under 313226 each coordinate is doubled. These are different footprints, not simply a reordered list.

At the lawful center `(-11,-7,-1)`, with the actual caster west-reference orientation, ordinary hours all have valid native selected columns. The larger footprint excludes hours 1547 at `(-13,-11)`, 1549 at `(-9,-11)`, and 1552 at `(-7,-5)`. The diagnostic contains no family315 child dispatch for these excluded columns; all dispatched hour placements report actual walkable cells and successful results. Native eYg.at performs the QI.R/X/aK filtering before child delivery.

The final test therefore uses the twelve explicit exported points and an independent west rotation `(x,y) -> (-x,-y)`, then reads attested native column heights. It requires exact reference-to-position equality for every valid hour, absence and no child delivery for every excluded hour, twelve baseline hours, and mutually exclusive passive/control branch selection. It does not call the production geometry helper as its expected-value oracle. The focused test is delegated; this paragraph does not claim a terminal pass before that result exists.

Terminal qualification: the corrected independent west rotation is `(-x,-y)`, not `(-y,-x)`. `test_combat_xelor_dial_passive_runtime` passed **1/1** against actual PostgreSQL release `677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d`, unchanged at start/end. Test SHA256: `2fdb8ceb51cb6e3efde9af3c4a6ae76826736892363e24542d56e613e4ddc08f`. Evidence: `.runtime/xelor-readonly-20261011/dial-passive-rotation-corrected.log`. This supersedes the earlier common-complete-center expectation and the incorrect transposed independent oracle. It qualifies actual passive/control casting and exact selected terrain geometry; it does not certify client rendering or all other Xelor passives.
