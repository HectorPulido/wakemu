# Class flow checkpoint — 2026-10-07

This checkpoint separates access, construction, and reactive gameplay. None of
these counts is an overall spell-completion percentage or a deployment result.

## Ready and temporary spell access

The offline `class-spell-grants-ready-access-03.json` audit exercises the production
Ready entry and native start event for all 18 classes at levels 1 and 200, with
full HP and no equipment. Source and tool hashes remained stable during the run.

- 34 of 36 cases reached Ready and start; breed 3 at both levels still rejects
  `IsControlledByAI` because its native predicate is unsupported in that snapshot.
- 116 actual granted spell UIDs resolved through their owned books. All 116 were
  rejected as expired after their actual grant was removed.
- 70 cast attempts prepared transactions. Preparation does not prove execution,
  state transitions, damage, or graphical correctness.
- The earlier six Cra beacon attempts no longer fail with missing event-target PV.
- All cases retain `gameplay_verified=false`; the deployment gate is false.

Report: `.runtime/combat-review-20261007/class-spell-grants-ready-access-03.json`.
SHA-256: `530882ab8b6f3bfd3ca58371de049517ab39c2950b35a4b6f6b5c2663505ac44`.

The next Ready snapshot, `luna-grant-ready-04`, confirms the AI-control predicate
fix: the same two breed-3 cases now reach effect family 325 and reject its missing
handler instead. Ready remains 34/36, with 116 owned grants and removals, and
75 prepared transactions. The source-derived healing flags are included. No
gameplay or deployment gate passes. Subsequent family-325 integration and
complete empty-summon count fixes require a new measurement.

Report: `.runtime/combat-review-20261007/class-spell-grants-ready-access-04.json`.
SHA-256: `a8d79442606e109bc84b5ec0e9240a985fa1c7b18667bc8ab551cd4e538a0f8a`.

The latest completed broad run is `luna-grant-ready-06`: 34/36 Ready, 116 owned
grants resolved and denied after removal, and 79 first transactions prepared.
The two breed-3 cases now reach family 325 but reject an incomplete retained
view during its application events. The subsequent insertion-order fix is
under focused validation. This supersedes the older missing-handler and
missing-baseline diagnoses; it does not establish 36/36 Ready yet.

The state follow-up audit observes 48 distinct changed state references in
actual transaction drafts, with 30 further transactions prepared and 156
rejected. Its captured selector is limited to literal state dependencies.
A subsequent selector also considers actual newly added grants, but requires
another measurement. These counts prove neither committed gameplay for every
case nor complete state-transition coverage.

Report: `.runtime/combat-review-20261007/class-spell-grants-ready-access-06.json`.
SHA-256: `7efa749b71d09e50298448f876b416f6bdf2b91046dc70bcf972f13a85194545`.

The signed-filter/wildcard count correction passes 35/35 focused condition
tests and nine original-Java filter assertions. Complete nonempty summon
counts still require current native death-component authority.

## Initial summon states and reactions

The six-profile snapshot `luna-summon-reaction-03` creates five profiles with
their initial states. Profile 3789 still rejects detached actor membership in
that snapshot; a subsequent shared property-authority fix requires revalidation.

The successful profiles are 3793 (breed 8, spell 8405), 3794 (breed 12, spell
4718), and 3798/3799/3800 (breed 9, spells 7793/7792/4807).

Its 23 damage dispatches are primary effects. Seven change HP from 1 to 0.
**No secondary retained-state reaction is demonstrated by that report.** Event
and retained activation tracing is being added to test that separate requirement.
The audit does not establish normal parent-cast permissions or alternate-owner
behavior.

Report: `.runtime/combat-review-20261007/class-summon-reactions-initial6-final.json`.
SHA-256: `02f259b7b7b2b90b47dccd96864765ca59c705f6a291b622c15b017f4a877818`.

A subsequent isolated run creates profile 3789 after the shared property-count
fix. Its seven primary damage dispatches return false; at HP 1, guards such as
`GetCharac("HP", "target") > 1` reject the effect. There is no demonstrated
reaction or HP/state change. This result does not replace a fresh combined run
of all six profiles. Constructor scope/rollback and property-count regression
tests pass 8/8.

Isolated report: `.runtime/combat-review-20261007/class-summon-reaction-profile3789.json`.
SHA-256: `c897772e6512e8f8da2504408b7f2d27bba5d177f15ecd0711cb99d236a799b7`.

The subsequent combined snapshot `luna-summon-reaction-06` supersedes the
constructor count above: **all six profiles are created** with stable source
hashes. It records 30 primary dispatches and 323 native events (93 during
construction and 230 during the damage probes), but zero retained activations.
Seven dispatches change HP from 1 to 0. Initial HP comes from native profile
characteristics and has not been increased to bypass conditions.

This narrows the shared reactive blocker: events are emitted, but no retained
listener is observed executing. Investigation must distinguish missing state
children from subscription selection and from an inadequate direct-leaf probe;
creation and event counts do not settle those questions.

Combined report: `.runtime/combat-review-20261007/class-summon-reactions-sixtrace-final.json`.
SHA-256: `823711a3683f9f49fb5867754577d2b71ab24561ec8d6fd740d69dabb5b8fc40`.

Source review identified an important limit of this fixture: it creates summons
without running production Ready for the owning class first. Cra reactive innate
state 3419 is consequently absent. Beacon initial-state children do not by
themselves replace the owner's damage listeners; state 1304 listens for healing.
Zero activations in this fixture therefore does not demonstrate a broken live
subscription path. The next probe must initialize the owner through Ready and
preserve the native parent spell roots and inherited area geometry.

## Latest focused evidence — 2026-10-08

The production-Ready, full-parent-root summon probe supersedes the earlier
reaction fixture. All six profiles are created; 30 parent dispatch attempts
produce 1,341 native events. Ten retained activation calls are observed:
nine return true and one returns false, in profiles 3789, 3793, and 3794.
The three Cra beacon profiles still have no demonstrated retained activation.
The sampled damage events do not match their subscriptions, so this result
requires investigation of the native event producer and cannot establish that
beacon reactions work or that a live subscription path is broken.
Normal casting permissions and resource commitment are outside this probe.

Report: `.runtime/combat-review-20261007/class-summon-reactions-sixtrace-02.json`.
SHA-256: `e6f3b6fa43fc7ba064ef7ae9d3aa1b221725f0207c56d129ee1b146e67727ebb`.

Focused class-3 execution now passes Ready, combat start, and the first NPC
turn. Its next failure was the family-349 cell criterion lacking actual QI
first-fighter authority. The general cell bridge now distinguishes occupied
and proven empty cells while preserving the original invocation context;
31 focused tests pass. A fresh production-path rerun is pending. The latest
broad Ready count remains 34/36 until that broader audit is repeated.

Captured-summon family 324 is connected to the owned roster, shared constructor,
native scaling, action book, codec, and checkpoint persistence path. Thirty-five
focused tests pass. Original exports cover 33 capturable profiles and 181 ability
trees, with 905 book checks. Transitive dependencies, level-zero roots, and eight
nested profiles still require closure; these are class-2 dependencies rather
than an expansion to standalone monster spell work.

## Remaining shared blockers

Priorities are the complete class-3 turn cycle, correct native beacon reaction
producers, captured ability dependency closure, and full class-state cycles.
Sacro regression fixtures now use real QI; two outcome expectations still need
native-source verification. Captured-roster migration 075 has not been applied.

No service restart, live database migration, or graphical acceptance test is
included. Manual acceptance remains a final whole-system step. Counts above
are scoped evidence, not a global functional completion percentage.

## Focused casting regression run — 2026-10-08

Current-worktree command:

```sh
PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_casting_range test_combat_range_conditions test_combat_conditional_costs test_combat_conditional_los test_combat_casting_eligibility test_combat_casting_alignment test_combat_casting_los
```

Result: 38 tests pass in 2.190 seconds. A separate 13-test run covering range
wire parity, range-flag import, cost overflow, and legacy self-cast LOS has ten
passes and three failures. All three self-cast tests omit the required shared
native casting query in their old fixtures and therefore stop before geometry.
They are being migrated to the actual producer without weakening its guards.
Neither run proves live client parity or whole-class functional completion.

## Class-3 turn-cycle result — 2026-10-08

The frozen `luna-ready-class3-qi-01` run now passes Ready and two actual turn
transitions, including registered summon actor 227. There are no recorded
failures; source and tool hashes are stable. This closes the previous
family-349 QI first-fighter blocker for this class-3 level-1 scenario.
It does not establish the full 36-case Ready audit or all class mechanics.
`gameplay_verified` remains false for this scoped mechanical audit.

Report: `.runtime/combat-review-20261008/ready325-qi-onecase.json`.
SHA-256: `81e5a4758302b14f33427c641644a33601a8099a95768498b86ee0f827b833f8`.
Snapshot manifest SHA-256:
`45bfeb34159b970bc17716a299e3c806d1315bbd9ee518e3826fdb704060ea1f`.

## Self-cast fixture revalidation — 2026-10-08

The legacy self-cast fixture now uses actual QI occupancy and
`NativeOwnedCastingContext`, native LOS geometry, and real usage metadata.
The same range-wire/import/overflow/self-cast command now passes all 14 tests
in 0.531 seconds. The native casting source does not establish a same-XYZ LOS
bypass; the regression verifies shared native geometry rather than introducing
that shortcut. Independent range, free-cell, and resource guards remain tested.

## General fixes and captured runtime integration — 2026-10-08

Expiration now includes group-only timers and the actual state managers on
active or retired areas. Focused expiry, timer, and remote-effect tests pass
15/15 in 0.015 seconds. The tests cover child grant removal before its carrier
and rollback when a required payload is missing; they do not certify every
state's duration formula or wall-clock scheduling.

The captured runtime projection now contains 41 profiles, 195 spells,
178 states, 21 areas, and 2,156 effects, with no native-missing references.
Original level-zero export covers 195 roots and 1,152 effects. The scoped
runtime import adds 1,151 missing effects after checking conflicts against
existing definitions. Eight nested profiles are constructor dependencies;
the eligible captured roster remains the original 33 profiles. Full normal
captured-book dispatch still requires production-path verification.

A server-owned normal execution origin is now explicitly selected at normal
transaction root dispatch, using the byte-verified original eVt constructor.
This is a declared Wakemu policy, not a recovered original-server callsite.
Incoming trigger/restore contexts are preserved. Eleven focused tests and the
original constructor/mutator byte oracle pass; general normal-cast integration
is the next validation step.

## Full Ready audit — 2026-10-08

The frozen `luna-ready36-01` audit reaches Ready/start and one acknowledged
turn cycle in all 36 class/level cases (18 native breeds, levels 1 and 200).
Source and tool hashes are stable. Of 124 grant rows, 116 owned UIDs resolve;
eight defer because their actual actor is not current.

All 348 targeted cast attempts reject in this fixture: 130 twI, 123 missing
GetFightModel, 80 twV, 11 twT, two missing Symbiot authority, and two twE.
Native eligibility results require their actual context before classification
as bugs; this audit does not prove successful spell gameplay. The newly
connected cast-event boundaries expose the missing GetFightModel predicate,
which also blocks the actual Cra callback regression before event1025.

The historical report's `deployment_gate_passed=true` means its Ready check
passed, despite all rows retaining `gameplay_verified=false`. The tool now
reports that scoped result as `ready_gate_passed` and keeps deployment false.
The original frozen report is preserved rather than rewriting its evidence.

Report: `.runtime/combat-review-20261008/class-spell-grants-ready36-luna-01.json`.
SHA-256: `3e64d154dd66c67c32a4dce2d4a7c34244dca78a9f465a8a745de135130aef25`.
Snapshot manifest SHA-256:
`0e44ed72b065af5fc2cadc4a11dd51c2c6ceb59bcc076b818ac126b85df5ff16`.

## Fight-model producer verification — 2026-10-08

The actual client decode chain is now recovered: bootstrap12847 signed kind
byte passes through cvb.eHb, ckP, and buS.a into fcz.Tv. A fresh ordinary
Wakemu Fight explicitly selects native PVE model2; successful placement
serialization binds the actual selected wire model to the same runtime field.
Existing kind14 remains TRAINING_FIGHT_WITHOUT_PENALTIES; it is not rewritten
to native DUEL65. The predicate preserves its exact zero-argument signed-byte
contract and keeps truly missing model authority distinct from native no-fight0.

Focused model-condition, complete bootstrap, and transaction-RNG tests pass
15/15 in 1.189 seconds. The previous 123 unsupported-predicate audit results
belong to the old frozen source; integrated casts require the new snapshot.

## Shared class-event predicate sweep — 2026-10-08

The bulk static sweep follows 629 subscribed roots for events1024/1025/1028
through 4,130 typed nodes and 1,507 raw criteria. Missing explicit routes are
HasActiveCosmeticId (38 references), GetHumanAlliesCountInRange (30),
IsFacestabbed (2), and one each of GetActiveCosmeticId, GetAlliesCount,
GetBooleanSystemConfiguration, GetEffectCasterOriginalController, and IsPvp.
GetCharacInPct is accepted by the syntax validator but still needs its numeric
runtime path. These are shared implementation gaps, not individually failed
spell counts. They are assigned in parallel by primitive family.

The target audit now uses the production validator to select actual eligible
cells, with a bounded search and explicit completeness markers. Unexpected
ValueError exceptions are classified as unresolved authority rather than proof
of an unavailable target. Focused eligible-target, distance-group, and LOS tests
pass 14/14 in 0.003 seconds. The next full audit must use this new tool source.

## Exact activation-mask scope and shared providers — 2026-10-08

The class-event sweep now uses Qa.beD activation masks specifically, rather
than any of the seven targeting masks. The corrected scope is 333 subscribed
seeds, 3,745 typed nodes, 1,425 raw criteria, and 69 function names. This
supersedes the earlier 629-seed scope above; the missing predicate list is
unchanged. Native human/allied count routes and actor-type authority are
connected. Focused team-count, original-controller, controller-area, and
distance-group tests pass 19/19 in 0.040 seconds.

Family1080 is connected through the shared group lifecycle, retention, and
native distance-based child level. The original JVM differential covers
48 cases/96 assertions with no Python mismatches. Family1008 shares native
eYQ construction but resolves the creator from the source caster's original
controller; source orientation, targeting, and wire caster remain distinct.
These scoped integrations still require normal class-cast validation.

## General casting regression checkpoint — 2026-10-08

Command: `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_casting_cost_overflow test_casting_range_flag_merge test_combat_casting_range test_combat_casting_eligibility_metadata`. Result: 13 tests passed in 1.404 seconds. This bounded run verifies signed cost overflow/category aggregation, casting range and flag selection, and eligibility metadata. It is not an end-to-end class or client certification. No service operation was performed.

### Shared aura-removal and team-count unit verification

`PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_aura_removal test_combat_team_count_conditions`: 7 tests passed in 0.001 seconds. Aura-removal evidence covers exact family selection and preflight rejection, not yet factory registration or complete retained lifecycle. The manual nine-card preparation/result tracker is `manual-representative-readiness-20261008.csv`; all manual executions remain pending.

### Range-category removal and native LOS regression review

Root rerun: `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_range_modifier_wire_lifecycle test_combat_condition_los`: 5 tests passed in 0.006 seconds. The category1066 regression proves category removal, no RANGE11/AP pollution, and13497→13560 removal delivery. Since RANGE11 remains zero throughout this case, that assertion alone does not prove restored effective category range or reconnect behavior; those stronger assertions were requested from the test owner. The LOS regression uses the current native ray/property authority rather than an obsolete callback.

### Effective range restoration and new area/affiliation units

After review, the range1066 lifecycle regression now verifies the next casting range changes6→8→6 through application/removal, independently from unchanged RANGE11/wire and AP. Root ran `test_combat_range_modifier_wire_lifecycle test_combat_affiliation_directional_area`: 3 tests passed in0.008 seconds. The latter verifies the new nominal813/1030 direction/affiliation behavior; production class-cast validation remains pending. The Osamodas commit-lifecycle audit is currently running in an immutable snapshot; no successful commit/lifecycle claim is made before its terminal report.

### Captured summon commit and actual turn checkpoint

Immutable snapshot `luna-captured324-commit-02` manifest `9a9f518bc741a3cd841357772fe24fbf776dcaba289cb618a2b918aa7db26287`: original owned7348 tree prepared and committed through actual Ready runtime. Report `ready-transaction04.json` SHA256 `200d466429d6738a7f8f320aacc3ac993c2b409850014134286eba58d91b10f1` records73 delivery packets/native action records, actual summon turn and controlled authority, preserved selected/unavailable slot3, and rejected re-invocation rollback. Abilities7356/7357/7358 were rejected against the fixed fixture target (twI/twV/twI); no ability or client gameplay pass. Next action is native eligible-target selection, not relaxing criteria. Structural inventory regenerated:151 registered,20 construction-gated,13 missing families; these counts are not functional completion.

### Native casting tables and cast-accounting checkpoint

Luna immutable snapshot `luna-cost-los-range-01`, manifest `f5a911cadc2db8009469ee6d2015dde41344c258ede501cb5e2198b5b2d702e2`:9/9 tests passed for installed conditional cost, conditional LOS and deck-conditioned live range; result JSON SHA256 `cd6899daca13095c1979db09933b63894eecb36be26a2d19da9f1c826456e733`. Root separately ran `test_combat_spell_usage`:6 tests passed in0.008 seconds, covering per-target/per-turn limits, personal turn reset, discarded previews, native XY footprint behavior and intervals. Potential historical retired-actor participation in usage validation remains under source review; no change was made from that suspicion alone.

### Triggered-spell argument, policy and cost checkpoint

Root ran `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_triggered_spell test_combat_triggered_spell_policy test_combat_event_costs`:15 tests passed in5.306 seconds, process exit0 confirmed. This bounded evidence covers native trigger arguments, explicit server execution policy and costs; the separate full factory runtime execution/rollback suite remains the integration gate. Cast accounting source review confirmed XY/no-Z footprint semantics are intentional; active native population vs retained historical actor bookkeeping still needs an exact producer fix.

### Ordinary withdrawal/death integration verified

Luna ran the two previously failing ordinary authority/departure integration methods from immutable `luna-withdrawal-death-02` (manifest SHA256 `50bdbc60f6a22b5c490f30b02f7d2c3a6943cbd3552ea2c61442cc2b4afe7c4a`):2/2 passed in58.84 seconds, process exit0. Result JSON `withdrawal-death-01.json` SHA256 `92217924f888a930d4b3c4832f4a70586c401aa483e2a6cacf5d8b6f8d2bcb6c`. This proves those registered death/departure and remaining-owner targeting flows, not Osamodas recall or all death variants. The separate per-target usage producer is now being aligned with actual native bak/PV population; native ignoring of Z is retained.

### First actual captured ability commit

Run05 result SHA256 `ad03c663a7f7acb9592ad74cdb281edb267f640220c28c4df8298e6e9dd12673` records original7356 committed on its legal owner target after actual summon turn,8 delivery packets. Source/tool stable. This is one ability, not the full captured book or client lifecycle. Its plan charges1WP but current audit only records AP/MP; explicit WP before/after assertions were requested.7357/7358 and cleanup remain pending and must not be inferred from the harness local `complete` label.

### Aura creation/removal composition correction

The426 integration snapshot exposed an unconditional new338 constructor callback mismatch (`register_applied` absent). The owner replaced it with explicit `register_applied_target_aura` registration and completed the316 callback through `register_applied_stat`; full factory rerun is pending a fresh frozen snapshot. Root ran `test_combat_target_aura test_combat_aura_removal`:6 tests passed in0.097 seconds. This verifies bounded aura constructor/codec/removal behavior, not successful full factory composition. Recall859 PR watcher notification is a real nonempty native callback; existing effect phases cannot be treated as its equivalent without a producer.

### Triggered native ability integration passed

Luna snapshot `luna-triggered426-06`, manifest `a1fa44c497e33ed42fa9ec808ba45dcf9d2bf9423873dce40c61458c4cfbfbea`: actual factory nested ability execution and full source/RNG/private-outbox rollback2/2 PASS in12.26 seconds, exit0. JSON SHA256 `a3eeeed167fedae918378d3aaea53c31b915e56e8239fb5161c2ee9506d03f4d`. This snapshot precedes subsequent338/316 refinement, so fresh combined aura/runtime verification is required for current-source proof. Root regenerated routes:155 registered,21 gated,8 missing; no functional percentage is inferred.

### Actual Cra Precision threshold reached

Luna snapshot `luna-cra-precision-02`, manifest `c7c3daf63fdb804702393599d6604639dd926b99bb5b65f9ae078ab38a0a07b2`: actual Cra20 Fulminante4820 cast against native5574 level133 HP4500 completed, HP4496 and committed state7792 level30. Report SHA256 `4724add88cac85f5e04571ed575a86d3f051bb85ee9cb6177e63fbbec8dd8050`; source stable. Enabling7752 beforehand did not build Precision in the tested sequence. The successful row stops immediately, so it does not prove threshold survives end-turn or enabling7752 afterward. Next verification is same-turn activation/conditional-wall cast/removal through normal resources and turns.

### Current aura and triggered-spell integration checkpoint

Luna snapshot `luna-426-aura-01`, manifest `3e8a569926fee3c4a368f54cc7f2669a6b922bf0094c5481c89049fe21560da7`: `test_combat_triggered_spell_runtime test_combat_target_aura test_combat_aura_removal`8/8 PASS in10.00 seconds, exit0. JSON SHA256 `29eb446b918d3262ba49d6222d077a4d534f860665a16236b6df323bb0902a47`. Covers the current snapshot nested426 dispatch/rollback and represented338/316 constructor/removal tests; complete class/cell/client acceptance remains pending. User authorization now explicitly permits world restart and live testing after changes and automatic validation are finished, followed by pausing the goal when that phase closes. No restart/live action has occurred yet. Extra-turn investigation found actor activation count incorrectly being used as native round; actual timeline-round producer and AP/MP observer ordering are being fixed together with separate ownership.

### Capture and temporary-book bounded units

Root command `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_capture_handler test_combat_morph_spellbook`:7 tests passed in0.007 seconds. These verify capture handler guards/slot/property transitions and temporary book construction semantics; they do not certify full capture or transformation class-cast flows. Capture320 factory registration was subsequently integrated and needs a frozen full factory test. The normal Pandawa6847 integration reached carrying but rejected distinct-recipient validation; its target selection/source contract is under review, without weakening that guard.

### Recall notification and remaining integration checkpoint

Root ran `test_combat_summon_recall test_combat_kill`:15 tests passed in0.486 seconds. Recall859 now uses an explicit fresh Wakemu PR completion policy, ordered optional watchers and UID deduplication; native client callbacks were identified as presentation/observation, not HP/roster mutations. Parent UID is deliberately separate from native parent phase index. This is bounded transition evidence; complete original recall and cleanup require normal class-cast integration. New808 resource observer,309 reflection,320 capture and933 temporary book routes were connected and handed to frozen snapshot validation. Sacro integration measured HP140 against an old expected60; source audit will decide whether production or golden data is wrong. No restart or live probe has been performed.

### Resource notifications and temporary-book verification

Root command `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_resource_pa_notifications test_combat_morph_spellbook`:9 tests passed in1.002 seconds, process exit0. Covers bounded ordered AP/MP listener and temporary book behavior; full resource integration triage is still pending. Profile5900 form dependencies require scoped ability trees as well as book construction data; this explicit import requirement was assigned to the graph owner and cannot be replaced by a book-access-only pass.

### Resource batch and true-round verification limits

Luna `luna-resource-pa-02` manifest `56983b2b8f41f93ca1c502ab59fd4d2ae92c3688e733badddc46aa8c7cbf719c`:38/38 resource tests passed in0.887 seconds; JSON SHA256 `c5d11ef00e456abff3235640ce2113c6e4b331f5dcad6ac59e5209365299df10`. Subsequent native source review found AP/MP expandable PA must preserve raw current beyond effective max, so this pass is not proof of exact808 semantics; raw-current authority/setters are now being corrected. Root `test_combat_additional_turn test_combat_table_turn`:9/9 passed in0.349 seconds, including actual double activation preserving round1 and native table turn until the complete cycle wraps, plus45 native insertion observations. Complete original class turn/area interactions still need integration.

### Turn duration and synthetic resource cost regression checkpoint

Root `test_combat_turn_duration test_combat_consume_resources` initially exposed an incomplete synthetic actor fixture (missing max_hp before923 consumption). The owner added actual HP/maxHP fields without changing guards. Fresh rerun:9/9 PASS in0.076 seconds. Includes explicit Wakemu668 turn-duration policy and exact synthetic eWf923 cost identity/delivery; duration consumer is an authorized server policy, not recovered original server behavior.666/667/668 central routes are registered and require full normal class/turn integration. Beacon reaction coverage M3 now has a dedicated owner to verify the complete owner-cast→beacon→secondary effect chain and removal.

### Updated usage and turn cross-check

Root `test_combat_spell_usage test_combat_additional_turn test_combat_turn_duration`:20/20 PASS in0.541 seconds on current source. Full ordinary class-cast coverage remains separate. Sacro healing expectation now source-proven: native416656 max330×1%×stored5 floors16; HP124→140. The owner froze a regression asserting the16-point delta, and integration rerun is pending. Beacon investigation distinguishes tooltip-only literalFalse formulas from executable reaction callbacks; an actual owner-cast trace is needed before claiming the reaction works.

### Actual target aura factory integration

Luna `luna-aura338-01` manifest `537b692b48af0b4e491cb301d42b91702b964ab1c4a2a7526c1144318abe7a1c`: `test_combat_aura_runtime test_combat_target_aura test_combat_aura_removal test_combat_triggered_spell_runtime`9/9 PASS in60.24 seconds, completed runner JSON exit0, SHA256 `b8885a9be96414922d8c3886f00adf654d85536c4e526840d15df5c560dcb242`. Owner stopped only its lingering private snapshot process after terminal runner report; shell cleanup exit130 is distinct from completed tests. Actual338 factory creation→316 removal and nested426 runtime represented by this suite now have integration evidence. Scoped308 audit found all seven class nodes create TRAP domains, so no-op copying on known empty-characteristic glyphs alone would not close actual class308; original trap subtype producer remains under implementation.

### Class-condition route inventory refreshed

Root rebuilt `build_class_condition_gap_inventory.py` after central condition additions:116 textual functions,130 structural native classes, zero textual functions without an explicit route, zero local parse failures. All116 remain classified partial because full argument/PV/lifecycle evidence is not certified; this is not functional completion. Root `test_combat_breed_in_symbiot`:4/4 PASS in0.002 seconds, covering all occupied slots independently from availability/selection, native short saturation, known null/non-eHP versus missing component, and evaluator argument/selector routing. Actual class casting and newly added conditions still require frozen integration verification.

### Raw resource and trigger identifier checkpoint

Root `test_combat_trigger_identifiers test_combat_resource_pa_notifications`:18/18 PASS in0.761 seconds. New raw-current producer preserves expandable/frozen AP/MP internal values separately from effective values, with ordered eWr callbacks. Native eLD reads its first PV argument directly (not trigger caster); eLF reads the actual triggering eWu state reference (not its container). Broader resource and class-cast integration remains pending. Actual beacon harness now exists for three matched element cases plus optional9-pair matrix; trap source has10 native PCs and requires a genuine partial-PV damage source rather than fake fighter stats.

### Sex/side predicates and carry release checkpoint

Root `test_combat_condition_sex_side test_combat_resource_pa_notifications`:9/9 PASS in0.696 seconds. Fresh predicates and raw resource behavior still require original differential/normal class integration. Pandawa6847 now carries successfully through the real owned-grant path, but preparing6848 fails checkpoint serialization; no release or full carry pass is claimed. The offending nonplain retained/transient field is under source-owner investigation. Captured profile5347 run06 actions are specifically7356 damage to owner,7357 empty-cell displacement,7358 owner-targeted effects; this must not be described as enemy damage or a generic buff.

### Carry checkpoint and wire regression checkpoint

Root `test_combat_carry_checkpoint test_combat_geometry_snapshot test_combat_snapshot_wire`:14/14 PASS in0.478 seconds. Carry-pair records now serialize explicit immutable typed gameplay fields without accepting arbitrary objects; actual6847→6848 integration rerun pending. Beacon source audit corrected profile3799 geometry to cross1 (not circle3) and found different runtime/display formula coefficients; normal reaction tracing and parameter semantics are needed before selecting a server policy. Trap actual bcY application hook is empty client-side, so its implementation must distinguish recovered center/owner/stat contracts from explicit Wakemu activation delivery policy.

### Feca creation/activation succeeds; expiration still fails

Luna M7 snapshot `luna-feca-glyph-01` manifest `75d3cae593627a4b68a345e95830357370223c0882be627ab47436c32b50059c`: actual6967 creates1474/1477, ordinary turn activation damages native enemy4500→4455→4410, but both glyphs persist after four real turn cycles. Report SHA256 `b9e750f33cd2b225143742698c0a748fa0eee6fccee3f1dc4f0cdeda41ce355b`, source/tool stable, lifecycle_failed. General registered-area timer/expiry ownership is being fixed, not a per-Feca patch. Root copied-book/sex-side bounded rerun8/8 PASS0.405 seconds. A new18-class production normal-cast audit has been assigned to exercise all safe classes while copy1002 remains unfinished; no Ready-only deployment claim.

### Registered area expiration omission identified

Feca investigation identified a general omitted producer/consumer: retained area records discard context timer, and runtime expiration precheck/due scan excludes area records. The fix must preserve actual area TimeDatas and pass registered area removal through the common lifecycle. M7 tracker now records this exact failed gate. Native PA→MP differential probe did not execute its intended mutation (MP stayed3); this is not a native equivalence pass, and its owner is checking setup.1002 codecs have two original byte-equal cases, but full character-copy construction/provenance remains incomplete.

### Recall wire guard and representative beacon correction

The actual recall audit now fails before recall assertions with `Native wire raw/effective current disagreement`; this is a real producer/serializer consistency gate introduced by raw PA support, and its owner is tracing actual AP/MP writer origins. No raw/effective guard is weakened. M3 manual text now avoids unproved matching-input-element restrictions; automated9-pair coverage is required, while Hector tests only3 representative arrangements. Native400 parameters encode a level0 signed-byte graphical status, not a damage amount; any separate beacon reaction implementation must retain display-only formulas as evidence and explicitly label server policy. General area timer storage/expiration/removal plumbing is implemented and awaiting focused plus M7 integration.

### Bulk baseline and current producer corrections

The normal-class audit now partitions 635 active spell/level pairs into 73 legal decks across all 18 classes at levels 20 and 200. This is a baseline denominator, not the full state, passive, conditional and summon-mechanic denominator. Its production smoke and bulk execution remain pending serialized validation. Dynamic grants are recorded separately, and manual graphical acceptance remains separate from prepared or committed transactions.

The summon resource discrepancy was traced to actual family950/1001 aliases writing effective AP/max while bypassing raw PA setters. These aliases now use ordered native resource setters; original recall and dragon transactions must be rerun before claiming the fix works in those flows. Catalog-free resource/wire smoke passed 55 tests on the shared live tree, without immutable-snapshot certification.

Root ran `test_combat_trap_area test_combat_area_damage_snapshot test_combat_area_timed_expiration`: 11 tests, 10 passed and one errored after 60.774 seconds. The error was a missing `level` argument to `wall_constructor`, not an expiration failure. Both area expiration cases passed. The owner corrected the constructor call using the captured level and added a missing-level guard regression; a fresh frozen suite and the original M7 lifecycle still need validation.

M3 now has source-proven state7802/7804 reaction branches, so HP changes alone must not be used as secondary-reaction proof. The audit requires a legal same-cell arrow after beacon cleanup with no secondary HP loss. Normal/critical state-child selection is under general source review; no additional synthetic beacon damage policy has been installed.

### Original recall and dragon transactions after raw PA correction

Recall02 now clears the wire guard, but the granted7348 transaction does not execute859. Report SHA256 `a494b3d641184ceada49690a9e7f4cdd95282f9565b2120525ddec5da3fae6fa`, stable source/tool. The source path requires occupied target cell and target state7134 from the owner. The next diagnostic revision retains target state provenance and full bounded effect traces before lifecycle assertions; no criterion is bypassed.

Dragon02 callback reports `both_native_grant_transactions_committed`: actual7349 at the owner cell costs2AP and adds7123, then after ordinary turn/ACK/cooldown progression a zero-cost7349 removes7123. Earlier target/cooldown rejections in that successful sequence are not a final blocker. Report SHA256 `cbb2f1533ca5b84682fe4826dfcca9761d1f46ba700aebbb526e58f1821a9b85`, manifest `fd6e7cfceee3b4c33af2441117240e10e962c25e022ebda46a875393592bcdf3`. This proves the represented state round trip; it does not prove graphical appearance, every temporary-book action or summon interaction.

Root catalog-free smoke `test_class_normal_cast_inventory test_combat_state_variants test_combat_character_copy_codec test_combat_character_copy_book`:17/17 PASS in0.012 seconds. This includes the baseline denominator summary separating rejected commits from prepared previews, and explicit Wakemu structurally paired normal/critical state policy using the causing hit rather than old creation critical. Original client default `guW=false` remains documented; that server policy is not presented as a recovered original caller. M3 fresh actual reaction/control integration remains pending.

### Complete normal baseline and root integration checks

The first immutable full baseline completed73/73 Ready cases and635 unique ordinary spell/level pairs:583 prepared,33 bounded searches without context,6 effect-transaction rejections and13 unresolved target-authority pairs. Selected commits85/85 passed;498 preparations lack a successful commit check. Separate130 unique grants produce262 observations. Report SHA256 `a0a233295760377eae42ac6c0d7108bf90b44dc1671c7e2fff518eff096c59c2`. Full results and scope limits are in `class-normal-cast-baseline-results-20261008.md` and `current-status-20261008.md`; no global gameplay completion claim.

Root corrected target-search classification of proven native alignment `twU` and PB50 `twJ` failures, preserving typed missing-authority rejection. Target-selection plus baseline inventory regressions10/10 PASS0.005 seconds. These classification changes do not change the historical baseline result. AP-property/usage/resource suite18/18 PASS1.726 seconds after the owner supplied real player identity in the fixture. Ready/runtime suite11/11 PASS0.445 seconds. The legacy server Ready call now supplies the same production expiration runtime factory as shared sessions; syntax passed. Actual nonempty area-child lifecycle still requires the M7 rerun.

### Beacon matrix and critical negative controls

M3 normal matrix02 ran all9 creation→arrow→6349→same-cell-arrow-control sequences successfully. Cleanup was verified and all9 controls had zero HP delta. Eight initial arrows produced secondary damage; contact7780 with AIR did not. Report SHA256 `1e4110e47a2d7167b31990da0af58fb4eb0c3fc37286a823ec5fb60c9347ba24`. Critical representative run completed the same four steps for3 cases, deltas AIR-5/EARTH-3/FIRE-3 and all cleanup controls zero. Report SHA256 `0122a3ade6cbd5333b1e2b1f42c547573709659748f4112788e5681c79c7bb2d`. Both used manifest `8367a906a7fff156d0137602837e11c88594ef7d406725b9b1973598a01bc345` and stable source. Overall rows remain rejected because the extra same-cell beacon recreation receives `twV`; cleanup/reuse criteria must be diagnosed separately. No graphical acceptance is claimed.
