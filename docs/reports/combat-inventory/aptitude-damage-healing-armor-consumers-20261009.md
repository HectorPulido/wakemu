# Aptitude damage, healing and armor consumers

Scope: shared class combat consumers. Initial source inspection used catalog release
`7071a8d8c8664e9e0d5fe8f44bf2a948d4138060fc1353ea70f65f2dcf00b568`.
Source extraction: `.runtime/combat-review-20261009/aptitude-source-current.json`.
This is a code/source inventory, not an assertion that every aptitude has passed
interactive acceptance.

| Characteristic | Actual consumer | Conditions and limits |
| --- | --- | --- |
| General/elemental mastery 20,21–24 | `items/equipment_damage.py`, `combat_damage_healing.py` | Element follows damage family; elemental component capped at 50,000. |
| Melee/distance 103/104 | `combat_damage_parameters.py`, damage/healing consumers | Radius-adjusted Manhattan distance; melee at most two cells; explicit native flags can independently enable both. |
| Critical/noncritical 52/102 | Same consumers | Actual execution variant, rather than a second random critical roll. |
| Back mastery 16 | `equipment_damage.py` | Actual BACK localization; neutral damage suppresses localization. |
| Single/area 105/106 | Damage/healing consumers | Actual runner flags and geometry. |
| Berserk 107 | `combat_damage_parameters.py`, healing handler | Actual HP plus virtual HP strictly below half of their maxima. |
| Healing mastery 18 | `combat_damage_healing.py:healing_amount` | Combined with applicable general, elemental and situational mastery. |
| Final damage 48 / indirect damage 101 | `equipment_damage.py` | `interpret_damage_flags` selects 101 only without flag34 and outside spell containers11/12; source final modifier floor −50, followed by target final resistance49. |
| Final healing 114 | `combat_damage_healing.py:healing_amount` | Includes live triggering-runner final modifier. |
| Critical/back resistance 95/17 | `equipment_damage.py` | Applied only to corresponding actual execution/localization. |
| Block 87 | `combat_ordinary_authority.py:native_block`, `consume_damage` | Integer draw 1–100; native disabling flag preserved; successful block applies ceiling of 80% damage. |
| Armor given/received 120/121 | `combat_armor.py:armor_amount` | Native coefficient mode controls each side; given bonus excludes self armor. |
| Armor cap 88 | `combat_armor.py` | Max-HP percentage less current armor, except native bypass parameter. |
| Raw barrier 100 | `combat_damage_healing.py:consume_damage` | Existing native arithmetic consumes source barrier before armor/virtual HP/HP; separate from aptitude 17. |

## Conditional aptitude paths

* **17, Barrier:** root165201 start-combat1003 installs listener136452
  (damage L2 event2, excluding REP28), then flat reduction164892/family430.
  The family999 level override supplies half the actual actor level. The point
  allocation controls the listener budget, not a flat characteristic100 value.
* **27, Received healing:** 136594→136596→136597 applies state3205 at
  six levels per point. State root136592 listens to heal L1 event1 and invokes
 136593/eZJ. Its criterion requires another allied healer and excludes self and
  the healer's original controller as target. This is a triggering-heal modifier.
* **36, HP as armor:** 303745 start-combat1003 dispatches HP-level groups
 164893/303746 and armor runners164894/303747. The criterion compares current HP with80,000. Native group mode1 uses
  maximum HP plus maximum virtual HP: coefficient0.04 per allocated point below
  the threshold,0.004 at or above it, followed by native level rounding and
  transmission. Summons are excluded. This is not barrier100.
* **39, Indirect damage:** 410103→410104 assigns101+10 per point and
 410105 assigns20+40 per point; assignment integration is owned by the catalog
  and build-stat audit.

## Confirmed shared blocker: level-scaled listener budgets

Original `eZR.bbj` initializes an **int32** execution budget using
`(int)((float)aZS() + (float)fRR() * cyc())` when `aZS() >= 0`; otherwise −1.
Before the r54 correction, metadata exported only `aZS()`, runtime stored that
base directly, and replay validated it as a signed short. Listener136452 has
base0, so the old implementation skipped its barrier branch regardless of points. A guessed per-aptitude budget would
conceal a general metadata defect.

Prepared additive source tools:
`sniffer/java/ExportNativeExecutionCounts.java` exports all definitions' actual
base/coefficient with a complete marker. `combat_execution_count.py` reproduces
Java float32 arithmetic and int32 conversion. Runtime integration must follow
complete metadata publication through the native catalog pipeline; unknown
coefficients must remain explicit authority failures. The runtime now computes the source-qualified budget at actual invocation level
and validates its int32 width. Pure count/import regressions passed 6/6; original
`eZR.bbj` was executed for 210 native cases, all passing.

Complete revision `b0ed79766ae57e6ef26aa9321d05642522cf4c3d9baf7a22a4ea9d3cefc6f219`
was activated with complete r54 and its rebuilt matching AI, preserving all 7,482 documents of the prior
7071 release. Only retained metadata and the event-replay fixture's embedded metadata changed.
The main document contains 178,337 definitions, document SHA
`faf761441eae5c4b3261b99ca46ecf7478b21e673cd9f8e64a9e2d45b8b78757`.
`stage_native_execution_counts.py` clones the full immutable release and refuses
an unexpected active revision. It never changes `native_catalog_active`.

Barrier listener136452 has actual coefficient1.0 and target-clock duration1.
Its points budget and exhaustion now have actual incoming player-spell acceptance;
unused-listener target-clock expiry remains an independent pending case. Original renewal caller is not recovered: parent165201 listens to fight-start1003
only. Installed English `content.33.165201` explicitly describes a point-scaled
number of reductions **per turn**. Flag17 is `BUFF_BYPASS_OUT_FIGHT_MAX`, not a
renewal flag.

`combat_periodic_aptitude.py` implements an explicit Wakemu server renewal policy:
remember the actual constructor of a self-owned type36 aptitude listener only
when its native count scales with level and its native target clock has unit
duration. At owner-turn start, after production clock expiry, recreate an absent
listener from its original allocation/container and source child closure. Preserve
a surviving listener and its remaining budget. Reevaluate the original root
criterion, guard repeated turn delivery, and persist the recipe and boundary in
`native_class_initializations` for normal checkpoint restoration. No turn event
is aliased to1003.

The complete census has nine level-scaled finite listeners, but intersecting the
actual 50-effect aptitude closure qualifies **only136452**. The other eight
cannot enter this policy through the owned aptitude allocation/closure checks.
The real two-player Barrier acceptance passed1/1, including first protected
hit, subsequent unprotected hit, execution-count exhaustion and periodic
reconstruction after the actual target-start clock path. It uses source-owned
Iop level200 spell4775. The timer's target identity is asserted; expiry of an
unexhausted live listener is not independently covered by this case.
Count/import/policy focal regressions passed11/11, and the coordinator reports
35/35 affected regressions passing. Deployment remains separate: r54 includes
the general native count correction; the renewal hook awaits the next complete
server build. Received-healing27 actual consumer acceptance subsequently passed with the shared
group transmission correction below; HP-as-armor36 targeted initialization also passed with actual armor+52.

Actual two-controlled-player regression now passes: target owns one Barrier
aptitude point, genuine fight/QI/class initialization creates its source
listener, the first legal4775hit produces0damage and consumes that listener,
and the second producespositive damage. This proves one-hit exhaustion;
per-turn renewal is separately tested in the current checkout and awaits deployment.

## Per-turn renewal verification

The installed original localization `content.33.165201` specifies reductions
per turn. No original server renewal caller was recovered. Wakemu now has an
explicit general server policy for owned type36finite level-scaled subscriptions
with one-target-turn timing, validated against the actual allocation and its
original root closure. The complete aptitude census has50effects and exactly
one qualifying listener; other scaled listeners cannot qualify accidentally.
The policy constructs an absent listener on its actual owner turn, reevaluates
the source root condition and never resets a surviving budget. Original
constructor recipes are persisted in existing class initialization metadata.
No turn event is aliased to fight-start1003.

Actual PvP acceptance1/1passed with genuine controlled actors, original class
initialization and legal4775casts. First damage0, secondpositive; the first hit
consumes the listener. Target-turn processing after charge exhaustion and renewal yield exactly one
listener, and repeated processing of that same turn creates no duplicate.
Eleven periodic/count/import regressions also pass. Renewal source is tested
but awaits the next complete coordinated deployment after r54.


Validation commands (catalog URL/password-file environment supplied separately):

```sh
PYTHONPATH=server:server/tests WAKFU_TEST_GRANTEDCAST=1 /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_barrier_pvp_runtime
PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_execution_count test_native_execution_count_import test_combat_periodic_aptitude
PYTHONPATH=server:server/tests WAKFU_TEST_GRANTEDCAST=1 /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_aptitude_initialization test_combat_cast_event_runtime test_combat_iop_cast_boundary_runtime test_combat_iop_preparation_movement_runtime test_combat_retained_areas test_combat_retained_groups test_combat_retained_cell_groups test_combat_retained_null_manager test_combat_retained_handler_interface test_combat_retained_area_314
```

Barrier acceptance source SHA:
`0418ffc7c73fcbffbe95bcbaf43ee1818bf2653b0e192183b213bd935815e5c8`.

Verification limit: the actual PvP case exhausts the listener before advancing
the target clock. It proves renewal after exhaustion, but does not independently
prove expiry of an unused live listener. That case is being checked separately;
existing native timer scheduling tests are complementary evidence.

## Consolidated 31-attribute verification matrix

This matrix separates source/reducer verification from actual combat acceptance.
`Reducer` means the catalog-derived legal-point reduction was tested; it does not
mean every consumer or all 18 class combinations were exercised. `Conditional`
means real initialization is covered, with a separate reactive consumer test.
`Source` means the consumer was inspected; no attribute-specific runtime
acceptance is claimed here. Manual acceptance is pending for every row. Native
maximum `0` means no individual catalog cap; category/level budgets still apply.

| Bonus | Attribute | Native cap | Source root | Assignment evidence | Combat consumer | Actual integration evidence | Manual |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | HP percent | 0 | 136429 | Reducer | HP snapshot | Not individually certified | Pending |
| 2 | AP | 1 | 136428 | Reducer | AP cost/turn resource | Not individually certified | Pending |
| 3 | MP and mastery | 1 | 136430 | Reducer | MP movement + damage mastery | Not individually certified | Pending |
| 4 | Range and mastery | 1 | 136433 | Reducer | Casting range + damage mastery | Not individually certified | Pending |
| 5 | WP | 1 | 136436 | Reducer | WP resource | Not individually certified | Pending |
| 6 | Armor given percent | 1 | 410102 | Reducer | Armor coefficient | Not individually certified | Pending |
| 8 | Damage inflicted percent | 1 | 137558 | Reducer | Final damage | Not individually certified | Pending |
| 9 | Critical chance | 20 | 136444 | Reducer | Critical selection | Not individually certified | Pending |
| 10 | Block | 20 | 136445 | Reducer | Block roll | Not individually certified | Pending |
| 11 | Critical mastery | 0 | 136446 | Reducer | Critical mastery | Not individually certified | Pending |
| 12 | Rear mastery | 0 | 136447 | Reducer | Back mastery | Not individually certified | Pending |
| 13 | Berserk mastery | 0 | 136448 | Reducer | Berserk mastery | Not individually certified | Pending |
| 14 | Healing mastery | 0 | 136449 | Reducer | Healing mastery | Not individually certified | Pending |
| 15 | Rear resistance | 20 | 136450 | Reducer | Back resistance | Not individually certified | Pending |
| 16 | Elemental resistance | 10 | 136451 | Reducer | Elemental resistance | Not individually certified | Pending |
| 17 | Barrier | 10 | 165201 | Conditional initialization | Damage listener budget/reduction | PvP first/second hit + renewal PASS; included in r55 | Pending |
| 18 | Lock | 0 | 136467 | Reducer | Tackle movement | Not individually certified | Pending |
| 19 | Dodge | 0 | 136468 | Reducer | Dodge movement | Not individually certified | Pending |
| 20 | Initiative | 20 | 136469 | Reducer | Turn initiative | Not individually certified | Pending |
| 21 | Lock and dodge | 0 | 136470 | Reducer | Tackle/dodge movement | Not individually certified | Pending |
| 23 | Elemental mastery | 0 | 137957 | Reducer | Elemental mastery | Not individually certified | Pending |
| 26 | Melee mastery | 40 | 137965 | Reducer | Melee mastery | Not individually certified | Pending |
| 27 | Healing received | 5 | 136594 | Conditional initialization | Incoming allied-heal modifier | Actual ally modifier+12 PASS; self exclusion PASS; included in r55 | Pending |
| 30 | Distance mastery | 40 | 137977 | Reducer | Distance mastery | Not individually certified | Pending |
| 31 | Flat HP | 0 | 137974 | Reducer | HP snapshot | Not individually certified | Pending |
| 34 | Critical resistance | 20 | 137557 | Reducer | Critical resistance | Not individually certified | Pending |
| 35 | Elemental resistance | 1 | 137559 | Reducer | Elemental resistance | Not individually certified | Pending |
| 36 | HP as armor | 10 | 303745 | Conditional initialization | Start-combat HP armor | Actual2 points/maxHP650: armor0→52 PASS | Pending |
| 37 | Willpower | 20 | 243129 | Reducer | AP/MP loss willpower | Not individually certified | Pending |
| 38 | Healing performed percent | 1 | 410101 | Reducer | Final healing | Not individually certified | Pending |
| 39 | Indirect damage and mastery | 1 | 410103 | Reducer | Indirect damage + mastery | Not individually certified | Pending |

Evidence scope:

- Source/reducer inventory: `aptitude-all-attributes-audit-20261009.json` records
  31 identities and rejects four dormant category references. Its historical
  validation is 10 passed / 4 isolated-Postgres skips, not 14 passes.
- Actual Barrier acceptance:
  `test_combat_barrier_pvp_runtime.BarrierPvpRuntimeTests.test_real_controlled_spell_hits_barrier_twice_and_target_clock_expires`
  passed1/1 against active b0ed. Current renewal/count/import batch passed11/11;
  the subsequently added checkpoint-roundtrip case awaits its own run.
- Shared affected class/retention regression batch passed35/35. This protects
  existing Iop/Cra paths without certifying each attribute's gameplay outcome.
- Received-healing actual consumer and generic dispatch batch passed13/13 in a
  fresh process; HP-armor corrected targeted case passed1/1 with actual armor+52.
- No screenshot/manual result has been reported for this consolidated matrix.
  Deployed r54 contains native count scaling; periodic renewal exists only in
  the tested checkout until the next complete coordinated build.

## Incoming-heal integration defect under validation

The real allied Healing Word779 case initialized state3205 at level12 but healed
16 on both the aptitude recipient and the control recipient. The incoming L1
listener136592 activated and child136593's criterion evaluated true. The final
modifier accumulator stayed0 because the child resolver returned no selected
PV, before the eZJ handler. This was not percentage rounding.

Original `eYg.a(Iterator,eVt)` offsets139–156 pass the group's target PV to
`eVn.a` when `rFn` (target transmission) is true in the actor branch. The shared
Python child dispatcher instead cleared `native_explicit_target` unconditionally.
This forced selector recalculation for the ally-directed eZJ child, whose native
fcE mask3 is SELF plus in-area. The general fix preserves explicit PV presence
only for an actor branch with target transmission. The existing child's native
`aZX` policy still decides whether to recalculate; criteria and handler guards
remain unchanged. Cell and nontransmitted branches retain no explicit PV.

Fresh-process actual allied-healing and generic dispatch regressions passed13/13
(97.066s). The ally with two allocated points now receives more healing than the
non-aptitude control; self-heal exclusion is checked. The affected Iop/Cra/group
regression batch remains pending after this general transmission correction.
This change is not part of deployed r54.

## Deployment and regression update

The coordinator reports that the other deployment agent's complete r55 image
now includes the group transmission correction and periodic renewal with matching
current source hashes. The earlier statements about those changes awaiting
deployment describe the preceding r54 checkpoint and are superseded here.

Fresh-process received-healing acceptance passed with explicit ally PV and actual
family258 final-modifier addition12; self healing has no such addition. The
subsequent affected aggregate ran64 tests and exposed two failures: HP-armor
initialization captured `execute_activation` rather than its direct child
`execute` (corrected targeted fixture passed1/1 with armor+52), and Preparation3462 genuinely remained
after the modified attack. The latter is under source investigation: native
409890 subscriptions now target the incoming enemy, marker151186 is absent, and
151188's marker-presence criterion rejects consumption. Native group transmission
must not be globally reverted or its guard bypassed to hide this regression.
No complete aptitude verification is claimed.

## Preparation compatibility policy after native target correction

A bounded original-client oracle instantiated actual definitions151184 and409890
and their actual eYg runners at level20. Both retain `rFn=true`, `rFm=false`
and `owner_on_caster=false`; there is no subtype/default exception permitting
reversion of transmitted PV presence. Original Qe construction defers aZN
subscriptions instead of executing their children immediately.

The previous target-selection defect accidentally enabled Preparation's consumed
marker on the owner. With correct target transmission, the source-declared
deferred marker subscription is installed on the incoming attack recipient and
does not produce marker151186 on the carrier. The existing1025 cleanup criterion
then rejects state removal. The original server's500 publication/compatibility
behavior is unavailable.

Wakemu explicitly completes this preparation recipe: after a real live faq
modifier mutation for the primary attack, validate its owned500 subscription
source closure, damage2 modifier branch and1025 native321 cleanup branch whose
criterion names a declared400 marker. Construct that marker on its actual owned
carrier once before normal1025 publication. The existing criterion and321 removal
run unchanged. Qualification uses source structure and current state identity,
not state/effect ID whitelists. Failed casts never settle; non-damage casts never
note a mutation; repeated hit modifiers yield one marker; an already removed
carrier is skipped. Unknown carrier authority still fails. The policy has no
new persistent runtime object; the actual marker uses normal retention/checkpoint
serialization. Initial actual Preparation acceptance and four pure policy cases passed5/5.
Final source additionally preserves every declared marker-ancestor criterion,
rejects probabilistic substitute branches, and bounds cyclic source paths.
Fresh combined acceptance against final helper SHA
`61d979c2f5bb26ccbc7f270e8e0d847ff7093ffbe27f5bf9c86dc0b8b8851f9a`
passed **16/16 tests in 49.189 seconds**. This includes the actual Iop preparation,
banner and environmental-area module, five preparation-policy cases, actual
received-healing27, Cra cast events and HP-armor36 initialization. The policy
also records distinct primary attack UIDs, so multiple recipients settle one
carrier marker without treating reactive damage as another primary attack.
Validation used a fresh process and made no database writes. Deployment of this
final compatibility policy remains the coordinating agent's separate step;
manual client acceptance and complete verification of all31 attributes remain
pending.
