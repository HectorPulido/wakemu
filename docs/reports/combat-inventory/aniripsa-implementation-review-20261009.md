# Aniripsa implementation review — 2026-10-09

This supersedes the inventory-only scope for the new implementation work.
Changes are local in the shared checkout. No world restart or deployment was
performed by this work. Live client acceptance is pending.

## Final local verification

The final combined gate passed **134 executed tests in 183.977 seconds**, with
zero failures and zero skips. It includes actual Cunejo1814 healing, guard
expiry and replacement, fresh area-object selection, dispatch/event replay,
and Cra, Iop and Sacrier regressions. Cra beacon checks passed9/9. Evidence:
`.runtime/aniripsa-implementation-20261009/combined-regressions-selectorbit64.log`.
This is local verification; no service restart or deployment was performed.

## Corrected general mechanisms

### Actual resurrection, separate from HP assignment

`combat_resurrection.py` connects a successful flagged196 restoration of an
attested OFF_PLAY corpse to IN_PLAY status, native death-state reset, timeline
reinsertion/counters and12727 state1 delivery. It preserves the registered QI
slot and the current fighter, avoids duplicate base-order insertion, and
consumes the saved removal record. Runtime delivery clears its prior death
suppression so a second real death can publish.

The bundled native inverse path is aTS1→buH.be→fbX.D→fem.rD and
fcb.D→fdt.bu. The original server publisher is unavailable: linking the
successful owned196 execution to this inverse boundary is explicit Wakemu
server policy. OUT_OF_PLAY final retirement is not silently resurrected.

The real three-player/Wonejo test kills an allied fighter with actual native
ability executions, interrupts the resurrection child to verify source/RNG
rollback, casts actual1535, checks1144, QI/timeline/state1, advances the restored
fighter's legitimate turn and defeats it again. It passed locally, including
the second death delivery. Property114/no-timeline actors and explicit movement
overrides are distinct unverified boundaries.

### Protected summon replacement

Súper Cunejo's native graph first creates a base summon, executes protected332
and tests whether the cell is free for its replacement. Previously protected
death left that exact summon IN_PLAY with a blocking QI slot; the sibling
spawn was rejected, committing a cast with no living Cunejo.

The general protected332 boundary now retires a registered summon only with
its exact protected-kill receipt, zero HP and KO clock0. It releases its QI,
timeline/count authority before the next sibling. Ordinary actors retain their
original protected-kill behavior; ordinary summon deaths retain settlement.
This removal boundary is documented server policy, not a claim that native
eZG itself mutates fdy. Four-profile and existing kill/retirement tests passed.

### Transmitted healing-recipient identity

The fresh-child relationship policy incorrectly reselected the caster for a
transmitted point PV using combined fcE mask3 (self+area). The caster lies
outside the allied recipient's point, so the allied received-healing modifier
was lost. Point mask3 now preserves Qe.g(PV)'s explicit-target contract.
Pure self mask2 still requests relationship selection; nonpoint beacon areas
still enumerate occupants. The original allied aptitude regression now passes.

### Conditional state-clamp termination

Repeated Cunejo death-area healing exposed a dispatcher failure after the
Propagador3869 accumulator exceeded the actor level. Native373487 checks that
overflow, removes the carrier through373488 and reapplies it at the bounded
level through373489. The carrier legitimately revisits373487, whose criterion
is now false. The dispatcher used to reject the repeated reference before
evaluating that terminating criterion, interrupting the turn.

The general immediate-cycle check now runs after native eligibility and
criteria, before probability and handler execution. The128-depth limit and
subscription recursion guard remain. Generic regressions cover terminating
false-criterion reentry and rejection of an unconditional recursive group;
the actual repeated area activation and previous-class gates are rerun after
this source change. This does not reset ancestry or bypass executable cycles.

### Fresh area-object selection during replacement

The second Cunejo death exposed another generic target-policy omission:
family843's fcE bit64 explicitly selects Qq area objects, but the fresh-child
policy enumerated relationship selectors without that object bit. It kept the
transmitted corpse PV, so `IsOwnSpecificArea(1814)` rejected it and left both
death areas registered. Fresh children now honor bit64 before explicit-PV
replay. Native Qq eligibility and the own-area criterion still filter selected
areas; there is no reference-specific deletion or ownership bypass. Ordinary
replay and transmitted point mask3 retain their existing contracts.

The generic target/dispatcher gate passed26 tests after this change, including
actual Qq selection versus transmitted actor replay and executable-cycle
rejection. The actual repeated-death replacement and prior-class gate are
validated in the final combined gate after this source change (134 tests passed).

## Verified gameplay and remaining acceptance

- Natural grants respect real level6; Contra Natura has its native state toggle,
  two-PW cost and same-turn rejection/rollback. Its separate matrix passed
  36 cases across three elements, self/ally/enemy and normal/critical casts,
  including illegal-self rejection and source/RNG rollback. The current
  native catalog changes healing modifiers rather than reversing allegiance.
- All four Cunejo profiles passed five expanded pipeline tests covering ten
  profile/action combinations, real books, ownership, QI, healing/debuffs,
  push, swap, sacrifice, cooldown, reinvocation and interrupted replacement
  rollback. The client rendering of the ephemeral base summon during an
  upgrade remains a manual acceptance item.
- Injured self/ally healing779, fullHP saturation, Vínculo781 state/cost and
  enemy rejection pass. Water779/780/625 heal allies and damage unobstructed
  enemies under both normal and critical variants, with once-only payment and
  immutable source previews. Juventud's self carrier scales to600 at200.
- All five marks have actual consequence and consumption assertions in the
  expanded seven-test mark suite. Explosana3882 detonates on a real death;
  Ting3884 reacts to threshold damage; Hmill3885 reacts to point damage and
  excludes zone damage; Reintegro3888 reacts at the qualifying allied turn
  end; Breo3919 copies healing and converts its full-health carrier. Native
  corpse guards and mark UID identity are preserved.
- Retraso5451 changes qualifying healing42→21, stores21 in3899 and releases it
  on actual voluntary movement1005. Family430 modifies a triggering runner;
  the earlier inventory's label “delayed execution430” was incorrect.
- Fuente salvadora creates owned area1812 at the selected cell and expires
  through actual turn boundaries.
- Paroxismo Vital affects self received healing, Todos para Mí adds its native
  initial health, and Elixir de Viento consumes actual positive tackle while
  respecting a zero-tackle negative control.
- Eleven utility/air tests passed for Colimador, Desfase, Juventud, Infusión,
  Vivificación, Prohibición, Psicosis, Aletargamiento and Matraz Infectado.
  They assert actual modifiers/carriers, normal/critical values, HP-dependent
  damage, capped healing, native mode conditions, actual turn expiry and
  rejected-cast snapshot/RNG preservation. Their report lists the narrower
  downstream branches were then tested separately: real Ready armor196 is
  removed by Prohibición while the caster heals245; actual Gangrena turn end
  damages its carrier84 and returns83 life; a real blocked Repulsión adds25
  collision damage with Colimador versus zero without it. The final exact
  assertions passed three tests in20.161 seconds.

These are scoped measured assertions. Catalog presence and a completed cast
are not proof of every tooltip branch. Detailed passive/summon coverage and
the final combined regression results are recorded below when frozen.

## Current inventory disposition

| Inventory item | Current local result | Acceptance boundary |
| --- | --- | --- |
| ANI-01 resurrection | Lifecycle correction and real death/revival/second-death tests pass | Restored client movement/casting, reconnect and presentation |
| ANI-02 allied healing | Actual recipients, modifiers, caps, link and rejection tests pass | Equipped builds and remaining link reactions |
| ANI-03 Contra Natura | Natural grants, toggle and36-case elemental matrix pass | Live books/reconnect and remaining combinations |
| ANI-04 marks | All five actual consequences pass | Cross-owner and simultaneous nested deaths |
| ANI-05 Cunejo | Four profiles, ten action combinations, death/resummon and death area pass | Client rendering, foreign-owner area permutation |
| ANI-06 passives | All20 have scoped positive gameplay evidence across the linked suites | Remaining radii, levels, critical and build combinations |
| ANI-07 retained/areas | Retraso movement,3907 enemy end, Fuente expiry and1814 replacement pass | Disconnect and alternate timer combinations |
| ANI-08 shared combat | Existing local runtime/prior-class regressions pass | Two-client PvP/PvM, dungeon return and previously observed duplicate map objects |
| ANI-09 boundaries | Target rejection, RNG/source rollback, caps, numeric and collision tests pass | Exhaustive map/height/large-actor and equipped-stat permutations |

This is readiness for complete manual acceptance, not a claim that every
possible combat combination or client session has been certified. Aniripsa is
not added to the accepted3/18 until the user accepts the manual result.

## Evidence

The combined local regression gate passed **100 tests in 249.440 seconds**.
It covers allied healing and elemental branches, marks, passive probes,
resurrection, explicit target selection, healing handlers/parameters/areas,
aptitudes, protected kills, summon retirement, runtime delivery, Cra beacons,
Sacrier Sacrifice/Columnata/thresholds and Iop casts. The beacon audit verified
all nine cases, including reactions, cleanup and reuse of the released cells.
The later expanded Cunejo and Contra Natura suites are separate gates; this
count does not claim their inclusion.

A separate frozen rerun passed **15 tests in 228.439 seconds**, with no failures
or skips: expanded Cunejo (five), Contra Natura (one method/36 cases), all marks
(seven), Cra beacon regression and allied aptitude healing. Evidence:
`.runtime/aniripsa-implementation-20261009/final-expanded-wrapped.log`.
The utility suite independently passed **11 tests in 66.351 seconds**. These
gates overlap the earlier regression gate and must not be added as a unique
test count.

The corrected seven-test passive suite passed again in52.625 seconds with no
failures/skips. Evidence:
`.runtime/aniripsa-implementation-20261009/passive-expanded-rerun.log`.
Its 7993 assertion checks that healing temporarily grants DODGE while3869
exists and that consuming3869 removes that bonus, while applying3903 to the
hostile recipient. It does not expect the consumed temporary bonus to grow.

Independent final verification also passed the remaining passive suite
(seven tests,33.164 seconds) and summon-passive suite (four tests,42.913
seconds), without failures or skips. The former covers actual Cura Única,
Marcador de Serie, Punción, Resplandor, Presencia, Anbareul and Secreto de
Producción's later3907 damage. The latter covers Naturaleza Muerta's three-PA
cost/death area in all four profiles, Transgresión's mode-dependent75
resistance and Ambivalencia's targeted ally healing and hostile reaction to
actual direct healing. Direct damage alone does not trigger that reaction.
Evidence: `passive-remaining-wrapped.log` and `summon-passive-wrapped.log`
under the private evidence directory.

The final area1814 dependency test passed after correcting both conditional
clamp termination and fresh Qq selection: a real Cunejo death creates the
area, actual area-enabled turns heal100→131,3918 expires/reapplies with a new
UID, Propagador stays capped, and the next actual Cunejo death removes the old
area through843 while registering one replacement. Healing1084 is light
element, with base24 at level200; it is not a24-percent-HP heal. The prototype
has no timed removal mask, so replacement is the relevant lifetime contract.
Production passes the enabled area callback policy from the world adapter;
an earlier fixture omission of that callback was corrected, not patched into
production. Full foreign-owner-area survival remains a separate multiplayer
permutation; the actual area ownership predicate has a negative-owner control.

The native runtime tests use the existing catalog/database with
`WAKFU_TEST_GRANTEDCAST=1` and `PYTHONPATH=server:server/tests:server/tools`.
The module roster is described above; output is in the private
`.runtime/aniripsa-implementation-20261009/combined-regressions.log` evidence.
No client rendering, network reconnect or live dungeon acceptance is implied
by these local assertions.

To reproduce the class-focused local gates from the repository root with the
existing verification virtualenv and local catalog database:

```sh
PYTHONPATH=server:server/tests:server/tools WAKFU_TEST_GRANTEDCAST=1 \
WAKFU_DATABASE_URL='host=127.0.0.1 port=15432 dbname=wakemu_runtime user=wakemu' \
WAKFU_DATABASE_PASSWORD_FILE="$PWD/.runtime/local/secrets/postgres-password" \
/tmp/wakemu-combat-review-venv/bin/python3 -m unittest \
  test_aniripsa_allied_healing_runtime test_aniripsa_healing_branches \
  test_aniripsa_contra_natura_matrix test_aniripsa_grant_summon_pipeline \
  test_aniripsa_mark_pipeline test_aniripsa_passive_pipeline \
  test_aniripsa_passive_remaining_pipeline \
  test_aniripsa_summon_passive_pipeline.AniripsaSummonPassivePipelineTests \
  test_aniripsa_cunejo_area_pipeline.AniripsaCunejoAreaPipelineTests \
  test_aniripsa_utility_pipeline test_aniripsa_utility_triggers \
  test_combat_resurrection_runtime
```

Catalog finalization can be expensive in this environment. Recorded final gates
disable Python cyclic GC while running unittest, flush its summary and exit
with the test result; this changes the verification process only, not combat.

- [Catalog and original backlog](aniripsa-complete-review-20261009.md)
- [Allied healing scope](aniripsa-allied-healing-review-20261009.md)
- [Marks, source values and areas](aniripsa-mark-source-pipelines-20261009.md)
- [Natural grants and four Cunejo profiles](aniripsa-grants-cunejo-pipeline-20261009.md)
- [Passive source pipelines](aniripsa-passive-source-pipelines-20261009.md)
- [Utility and air gameplay](aniripsa-utility-runtime-review-20261009.md)
- [Actual armor, Gangrena and collision triggers](aniripsa-utility-triggers-review-20261009.md)
- [Complete manual acceptance](aniripsa-manual-acceptance-20261009.md)

Private test logs are under `.runtime/aniripsa-implementation-20261009/`.
Full current server Python compilation and `git diff --check` passed.
