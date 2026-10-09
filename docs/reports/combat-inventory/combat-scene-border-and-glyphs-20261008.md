# Combat scene borders and additional glyphs — 2026-10-08

## Native border and local selection policy

`QI.P(x,y)` identifies the actual serialized mask bit128. `fbg(QI)` builds the faP footprint from those cells; `buM` uses the same predicate for border rendering. Bit128 alone does not block movement: QI.g checks256|512. faP.h adds512 only for an explicitly blocking template. The installed template46 has no parameters, hence its constructor blocking flag is false.

The compact PvE encounter selects its perimeter by a **Wakemu policy**: valid selected cells with a cardinal neighbor outside the selected XY set. This is not a recovered official map perimeter algorithm. Native selected surface indices remain intact beneath bit128. Duels retain their prior policy. Interior bonus placements are not guessed from this perimeter.

## Mirrored gameplay

The native cvb consumer buS resolves template46, constructs fbm with UID=cvb.myp, QI minimum XYZ, null owner, level0 and direction NONE, clones faP, installs its fbg shape and registers it in Qs. Server `combat_battleground_border.py` mirrors that constructor after the ordinary actor/QI initialization boundary, before the first combat runtime executes. It preserves a real area PV; no player is substituted as its owner/caster. Repeated factory construction preserves the existing clone and does not reset its children.

The existing published template46 record subscribes to10001/10008/10000 and owns root152027. The existing native area-effect tree supplies root152027, its real child3641 (family48 MP loss parameter2), and once marker152028 (family400, target-turn duration1). The root criterion is `not HasEffectWithSpecificId("target",152028)`. Existing shared area lifecycle/dispatcher/retention/timer machinery executes those definitions. Executing the children on server area callbacks and using the actual faP PV as their source is explicit Wakemu server policy; the unavailable original server callsite is not claimed as recovered. The MP parameter is **not a promise of two actual MP lost**: native eVZ willpower arithmetic and rounding still apply. A faP source has no PA characteristic (`faV.a(PC)=false`), so caster willpower is exactly zero; the target retains its actual stats. Missing/unrecognized source PV authority remains an error.

The old probe also printed39407/family1095. This is generic eWQ healing-percent, not a missing special border handler. It is not listed in the published template46 root or current152027 children, and is not enabled by this integration.

## Additional glyphs and scene data

`cvb.myK` carries additional area descriptors consumed by buS/fec; these are separate from the faP border supplied by myo/myp. Actual class-created glyphs continue through their existing faY provider and native area application packets. No authoritative map-to-additional-glyph placement list, official random bonus selection or encounter-specific spawning rule has been established here. Therefore no additional interior glyph or invented bonus effect is emitted.

`fdA.e/eI` serializes the fdy fighter-status map. It is not a permanent-glyph descriptor blob; an empty field cannot be used as evidence of missing scene glyphs.

## Evidence and validation scope

Native private dumps: combat-bootstrap-consumer.txt (buS faP construction), issue16-faP-live.javap.txt (constructor flags/shape), combat-QI.txt (P/g/bdZ), border46-effect152027.txt, terrain-effects-registry.txt (1095), native-runner48-eVZ.txt, native-area-faV-current.txt. Public installed sources: native-effect-areas.json area46 and native-area-effect-trees.json refs152027/3641/152028.

Constructor, topology consistency and original callback identity are covered by test_combat_battleground_border. Existing geometry/bootstrap/area-event/resource-loss regressions pass (45 tests,0.848s). The complete border module passes5/5 regressions, including the production dispatcher: MP3→2, original secondary state5227 and marker152028 exactly once. The raw callback preserves its explicit target; selected child invocations normalize that bit as usual. A separate24-test stat/ordinary-event run also passes. No manual client acceptance has yet been recorded; visible tint and actual movement/resource behavior require the combined build.

Runtime inspection at19:06UTC found image dynamic-complete-20261008-r29 lacks combat_battleground_border.py and has the pre-provider area contracts. Its visible border therefore has no matching server callback; the observed zero-loss live behavior cannot validate this new implementation. Deployment requires the coherent source set, without interrupting an active fight.

## Deployment update

The coherent provider and geometry are deployed in complete-20261008-r31. The general OwnArea selector also accepts the registered faP null owner as a nonmatching area instead of rejecting the entire query. Automated constructor/effect/selector checks pass; live border resource acceptance remains pending. Interior additional area selection is still independent work.

## Interior environmental point: local policy

The official map-to-glyph placement algorithm remains unavailable in the installed map inventory. A separate explicit local policy, `wakemu.compact-interior-range-v1`, now places one native point glyph 910 on the free interior cell closest to the compact encounter center. It excludes the perimeter and original participant positions, uses the actual selected XYZ surface, and omits the glyph when there is no free interior cell. Duels and encounters without the compact perimeter policy are unchanged.

Prototype 910 is the original `Zona descollada` (visual 800292), not a fabricated effect: entry masks 10000/10001/10008 run root 152452, whose native criterion requires `IsCharacter("target")` and no existing 152453. Child 152453 is native current-stat gain family160, RANGE characteristic11, parameter4. Exit mask10002 removes the child through the original Qq PL ownership ledger. The gain has no synthetic duration or repeated stacking rule.

The client constructor is `cvb.myK → buK.a → fec.a → fbm → faY`, with NULL owner, level0, NONE direction and obstacle−1. The server mirrors this as a distinct registered Qs PV. The local policy executes its original child definitions from the environmental PV rather than borrowing a player owner. Bootstrap, spectator and owned reconnect snapshots serialize the same actual glyph identity and mutable faY appearance; they do not execute its effects during snapshot construction. Removed clones are not recreated by subsequent runtime construction.

Area426 is localized `Bonus`, but its native effects explicitly require team1 and breed2534 and remove the area afterward. It is encounter-specific and is not used as an arbitrary general bonus. Other prototypes and official placements remain inventory items, not claimed implemented gameplay.

Initial verification: 2 interior placement/codec tests pass; the existing border+bootstrap suite passes13 tests. Production dispatcher gain/exit validation is recorded separately when complete.

Final focused runtime validation: `test_combat_environment_glyphs.EnvironmentGlyphRuntimeTests.test_range_glyph_entry_repeat_exit_and_checkpoint_myK` passes (1 test, 25.6 seconds). Actual original roots execute through the dispatcher: RANGE0→4 on10001, repeat10000 preserves4 and the same owned child UIDs, exit10002 restores0 and removes152453. Checkpoint JSON preserves the constructor and myK identity. The test exposed and fixed a shared eWQ/eWR consumer admission gap: a certified registered area PV is now accepted as caster, matching the existing stat handler; the recipient still requires an actual actor.

The native NULL-owner faY clone retains its default aBn reference point (0,0,0); this is serialized in faY.fTl, independently of the physical glyph XYZ in fec.f. The point shape does not depend on that reference. The exact codec policy tests pass after this correction.

Production is frozen for a future combined release. Release r32 intentionally contains only the map-cell budget update and does **not** include this interior glyph implementation. Do not treat source verification as a live glyph gameplay result.
