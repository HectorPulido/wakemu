# Resource snapshot and native sphere fixture review

This read-only review separates two original-test failures from gameplay engine regressions. No server source, test checkout, catalog or service was changed. No native catalog loader was started during the exclusive V9 gate.

## Resource snapshot movement

Original selector: `test_combat_effect_resolution.EffectResolutionTests.test_resource_snapshot_tracks_spending_movement_healing_and_turn_reset`.

The fixture creates synthetic actors and initializes only the mover's `effect_stats` HP/AP/MP. `Fight.move` therefore enters the native characteristic movement path, which requires a typed `native_rail_movement_authority`, explicit radius and dodge PC8. `combat_tackle_movement.py:57–69` deliberately permits the legacy no-characteristic fixture path only when `effect_stats is None` and no native global population exists. Supplying partial characteristics is not proof that tackle is zero.

The staged correction uses the existing typed `test_combat_tackle_movement.Authority`, radius0 and mover PC8=0. Other synthetic participants have an explicitly empty characteristic map, so they lack PC7 and are excluded by the source-backed native fef filter (`combat_tackle_movement.py:128–132`). This is a resource-sync unit fixture, not a claim about actual monsters' tackle statistics. The spending, real movement, damage, healing and turn reset still execute normally. Exact HP80/AP4/MP2 and subsequent HP80/AP6/MP3 assertions remain, with the declared PC8=0 included.

Prepared replacement: `.runtime/class-closure-20261011/fixture-staging/test_combat_effect_resolution.py`, SHA256 `25bc5b3cffb1954e3af9344f314f4ece1a2391c0c5d1ecb33331304349de8e76`. No production guard relaxation is appropriate.

## Sphere current-hour center

Original selector: `test_combat_summon_entry.NativeSummonEntryTests.test_native_granted_sphere_common_entry_and_registered_roster`.

The original assertion expects14 areas immediately after actual5345 creation, then manually invokes352198 to create the missing current-hour center. The actual unchanged-test probe records15 areas already present: twelve hours1546–1557, center1558, environmental910 and border46. State6759 is level12. Source closure includes6759→313305→313306 (`IsOwnSpecificArea(1557)`)→313307→313308 family315. The center is the actual313308 result, colocated with hour1557. Relevant frozen source extract: `xelor-passive-semantic-status-20261011.json`, records313305–313308; actual receipts: `.runtime/class-closure-20261011/fixture-staging/sphere-actual-inventory.json`. Probe before/after hashes confirm the original test was unchanged.

The prepared replacement removes the obsolete manual center-creation step and asserts the automatic result precisely:13 owned references1546–1558, faZ/type1, center effect313308/class315, center cell equal to hour1557, keep_after false, no running manager, and6759 level12. It retains15 total areas including the native border/environment, thirteen family315 applications, one307 summon, exact AP debit, registered roster, subsequent real2251 producer replay,843 removal, source isolation, reconstruction and reconnect checks. This strengthens the contract rather than changing15 to a permissive count.

Prepared replacement: `.runtime/class-closure-20261011/fixture-staging/test_combat_summon_entry.py`, SHA256 `d07147f63532cef7bce8f78d0f42ffebe54b03ec81740a303681b722cbfdbffe`.

## Qualification boundary

`fixture-staging/staged-tests-current.log` records all five staged tests passing. That historical log does not contain complete catalog start/end and integrated15-source pin metadata; it must not be presented as the current V9 gate. The original checkout files remain stale and therefore still reproduce their known failures. Queue these same five staged selectors against the current integrated overlay after the exclusive V9 load ends, preserving original failed files and exact assertions. No new engine correction is indicated by these two traces.
