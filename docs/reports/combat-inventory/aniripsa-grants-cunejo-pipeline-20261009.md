# ENIRIPSA grants, Contra Natura and Cunejo pipeline

## Evidence and scope

The tests use `SpellTransactionTests.native_server_fixture(7, 200, native_qi=True)` with the published native catalog, actual class initialization, the encoded native deck and actual granted-action UIDs. No state, grant, summon book, turn counter or casting usage is synthesized. Test-only HP changes provide an injured ally for numeric ability assertions. Both the original Fight checkpoint and RNG are checked for transaction rollback.

Native `eZG.c` adds fight properties 19 and 12, emits evaluated application, assigns HP minimum and resets KO_TIME to zero. Its client bytecode does **not** prove a server fdy/QI removal publisher. The original server publisher is unavailable. Native Cunejo upgrade graph 371795/371804 executes family332 followed by a free-cell group 371797/371806 and replacement profile5533/1775. Before this change the base summon remained IN_PLAY and indexed in QI with HP0, so both upgrade paths committed with zero living summons.

The fix is an explicit general server policy for registered summons after an attested completed protected332 runner: exact fresh summon registration, protected-kill receipt, HP0, KO_TIME0, native identity and original QI slot are required before OUT_OF_PLAY and QI removal. It runs before subsequent sibling free-cell criteria. It retains the actor and durable registration, records distinct `protected_332_boundary.v1` provenance, and preserves ordinary fighters and ordinary post-chain death settlement. This is server policy, not a claim that client eZG directly changes fdy.

## Assertions

- Actual innate3911 grants7977/7978/7979 only from real level6. Level5 has no grants; level6 and200 retain raw native UIDs and correct granted level.
- Contra Natura7977 costs2WP, installs3867 and8020, rejects a second cast in the same turn without mutating checkpoint/RNG, and removes both states on the next eligible turn. Covered with no passive,7992 and7998.
- All four Cunejo branches create exactly one living summon:182/book986/state3863;1775/book5457,5458,5459,986/state3892;5528/book7988/state8029;5533/book5457,5458,5459,7988/state3892. Dark mode comes from Contra Natura3867, upgrade from passive7991.
- Each created actor has correct native caster/controller7, owner3, team0, exact inherited level200, complete raw-UID action book, player control and verified registered QI cell. Upgraded branches retire exactly one base actor, set its obstacle byte to -1 and release its QI identity.
- All ten ability/profile combinations execute in the summon’s actual owned turn.986 heals an injured owner100→142;7988 applies8030level50 and characteristic27=-50;5457 pushes the owner one cell;5458 swaps, heals, retires the summon and allows a fresh registered resummon after the native cooldown;5459 executes bloodletting with HP100→69 and3869.
- Injecting a failure after protected retirement restores the original checkpoint and RNG, including the QI population.

## Validation

First focused verification passed18tests in62.423s: the grant/toggle/four-profile scenarios plus the existing protected-kill and summon-retirement suites. Expanded ability, actual end/ACK/start turn lifecycle, cooldown-resummon and rollback verification passed all5pipeline tests in73.687s. Native table rounds are published by RuntimeMessages; the tests do not advance cooldowns by editing counters.

Commands: `PYTHONPATH=server:server/tests <review-venv>/bin/python3 -m unittest test_aniripsa_grant_summon_pipeline test_combat_protected_kill test_combat_summon_retirement -v` (18test focused pass), followed by `-m unittest test_aniripsa_grant_summon_pipeline -v` (expanded5test pass), with the read-only authoritative PostgreSQL catalog environment.

These tests prove the asserted server pipeline cases. Client rendering, reconnect delivery, all passive combinations, enemy targeting and critical conversion behavior require their separately scoped acceptance/regression runs; this report does not label every ENIRIPSA mechanic complete.

## Contra Natura elemental acceptance matrix

`test_aniripsa_contra_natura_matrix.py` passed1test containing36subcases in97.045s using the authoritative allied fixture at level200. Each of779(water),630(air) and645(fire) is exercised before/after a natural7977 toggle against self, an injured authoritative allied player and an authoritative NPC enemy, normal and critical. Exact HP delta, mark/state, once-only AP/WP payment and original checkpoint immutability are asserted. Illegal self-target air/fire casts additionally preserve RNG.

| Spell / target | Natural normal / critical delta | Contra Natura normal / critical delta |
|---|---:|---:|
|779 self|+42 / +52|+21 / +26|
|779 allied player|+47 / +58|+26 / +32|
|779 enemy|-93 / -116|-93 / -116|
|630 allied player / enemy|-156 / -195|-156 / -195|
|645 allied player|0 /0; no mark|0 /0; no mark|
|645 enemy|-86 /-107;3882level92/115|-86 /-107;3882level92/115|
|630 /645 self|Native twI eligibility rejection|Native twI eligibility rejection|

These are exact outputs of the stated fixture and catalog revision, not universal damage constants. Current Contra Natura3867/8020 changes characteristic/healing behavior; it does not invert ally/enemy targeting. The allied water values include the fixture recipient's12% healing received. Client rendering and passive combinations outside the listed coverage remain manual/separate acceptance work.

Command: `PYTHONPATH=server:server/tests WAKFU_TEST_GRANTEDCAST=1 <review-venv>/bin/python3 -m unittest test_aniripsa_contra_natura_matrix -v`, with the read-only authoritative PostgreSQL catalog environment.

## Additional passive consumer acceptance

`test_aniripsa_summon_passive_pipeline.AniripsaSummonPassivePipelineTests`
passed four real-pipeline tests in 64.256 seconds. These tests exercise consumers
of the passives rather than their inert family400 Ready installation markers:

- Naturaleza Muerta5455 changes Cunejo7978 cost from2AP to3AP for all four
  normal/dark/base/upgraded profiles. Repeated legal player630 casts, with actual
  turn advancement when resources run out, kill each summon. Death creates one
  area1814 at its death cell, owned by7, with captured affiliation0. The baseline
  without5455 creates no such area. Protected upgrade retirement does not create
  a death area prematurely. Each actual dead summon is retired from participation.
- Transgresión7992 grants characteristic27 resistance+75 only while the caster
  has Contra Natura3867. Toggle-off removes it and the mode's characteristic114
  healing-50. Actual779 allied healing is47 naturally and26 in Contra Natura.
- Ambivalencia7998 targeted at an ally leaves self mode3867 absent, grants the
  caster final healing+30, and produces actual allied779 healing59 instead of47.
  Without7998, the non-self7977 target is rejected atomically.
- Ambivalencia targeted at an enemy subscribes to channel3/event1, which is
  **healing**, not direct damage. Subsequent779 self healing42 produces8 damage
  to the marked enemy; allied healing47 produces9. Direct779 damage93 or630
  damage156 does not generate a second reaction. All outcomes use actual spell
  dispatch and installed native children371980/371981.

## Dependent death-area acceptance

`test_aniripsa_cunejo_area_pipeline.AniripsaCunejoAreaPipelineTests`
passed one actual-pipeline test in39.483 seconds after two general corrections
owned by the parent agent. The dedicated fixture explicitly enables production
area callbacks on actual turn providers; the earlier summon fixture did not.

A killed Cunejo creates1814. The injured owner starts its actual turn in the
area and heals100→131; state3918level1 appears. Family1084 is **light healing**:
4+0.1*level200 gives24base healing, then the fixture's healing formula yields31.
It is not24percent of maximum HP. The next actual turn expires the old3918UID
and applies a new guard;3869 stays capped at the fighter's effective level.
A later summoned Cunejo's actual death removes the old area through371990/843,
records its retired area manager, and leaves exactly one new1814.

The first additional turn exposed a finite native state clamp re-entry that
was rejected before its terminating criterion was evaluated. The general
criteria-before-cycle-guard correction preserves unconditional-cycle rejection
and the depth128 limit. Replacement then exposed omitted fcE bit64 in fresh
child selection: the inherited dead fighter was selected instead of Qq. The
general object-selection correction preserves explicit replay and the combined
self/point selector exception.

Area1814 has unlimited activation charges and no native removal masks. The
verified lifecycle therefore uses actual3918duration and explicit843replacement,
not an invented timed area expiry. The final suite also checks the ownership
predicate against this actual glyph: source7matches, source-7does not. A second
real Eniripsa's foreign glyph surviving replacement is not directly covered by
this fixture. These final two predicate assertions are included in the frozen
source submitted for the combined validation gate.
