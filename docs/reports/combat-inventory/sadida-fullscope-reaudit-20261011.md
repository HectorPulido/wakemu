# Sadida enabled-branch re-audit

This read-only review distinguishes the current 44-method aggregate from exhaustive branch execution. Server sources remain frozen. PostgreSQL revision677 is authoritative; no gameplay, catalog activation or service changes accompany this review.

## Existing executed behavior

The doll action semantics test executes5024/8138 on3747,5023 on3748,5021 on3749,5026 on3750 and5025/5356 on3751. It asserts damage, healing, control carriers, displacement, retirement and QI removal. These are substantive action tests, although healing fixtures establish coherent injury explicitly. Separate tests execute Superpoderosa5153, Voodoll8140 against owned doll and tree, real NPC lethal damage against Voodoll, and a second independent fight's book/QI isolation. The twenty-passive initialization loop is not counted as twenty complete semantic qualifications.

## Remaining qualification gaps

| Boundary | Existing evidence | Gap |
|---|---|---|
| Superpoderosa3746 | Seven-action book and actual5153 attack | Its other six actions are not executed on this profile |
| Return8138 | Actual3747 retirement with912 | Other profile return paths not individually executed |
| Poison914/919 | Actual native carriers, passive reactions and false-root negatives | Explicit downstream poison tick assertion missing from the reviewed focused methods |
| Critical branches | Most helper calls force `critical=False` | Automatic critical selection and most authored critical branches unqualified |
| New fight | Two independent doll fights preserve their own book/QI snapshot | Full multiplayer reset/settlement sequence is not covered by that test |
| Multiplayer areas | Shared generic ownership tests and individual area/passive tests | Two actual owners creating/consuming areas in one fight not exercised integrally |
| Reconnect | Shared generic framework has receipt replay tests | Sadida-specific book/UID/native constructor replay lacked a dedicated test |
| Process restart | Checkpoint serialization exists | Do not claim interrupted-fight restart restoration; current policy aborts interrupted fights |

These gaps are execution coverage limitations, not proven missing implementations.

## Staged actual-runtime candidates

`.runtime/sadida-fullscope-20261011/test_sadida_scope_candidates.py` contains three pending tests: normal914 poison tick on the actual target turn with an unpoisoned control; explicit normal/critical native914 branches with downstream tick; actual3748 birth followed by read-only owned reconnect preserving UID/controller/book and original birth receipt without gameplay mutation. The reconnect fixture isolates current-value overlays and does not certify the complete PA codec or client rendering.

The critical candidate checks authored branch execution with explicit critical selection. It does not claim automatic RNG probability coverage. Current PG roots58701 and378149 author3617 levels `4 + 0.48*level` and `5 + 0.6*level` respectively. State3617 roots378095/378097 listen to1001 and execute1083 children378096/378098; the state duration clock separately ticks at target turn end. Thus target-start poison damage and target-end duration must not be conflated.

Native source excerpts are stored privately as `poison-source.json` and `poison-trigger-source.json`. Staged tests are not counted as passing until Luna's serial runner terminates. No production fix is justified merely by these uncovered branches.

Expansion candidates now cover the six remaining3746 book actions with real acquisition/turns,8138 retirement across all five ordinary doll profiles with actual912, and two fresh Sadida owners creating distinct seeds in one fight. The second player's breed is selected in its fresh source before effective sheet, actor snapshots and Ready; no live authority is changed. The ownership scenario then attempts the other owner's seed, verifies it remains unchanged, consumes the local owner's seed and checks a fresh independent fight begins without those transient areas/dolls. This independent-new-fight check does not substitute for an end-to-end world settlement/login process.

All four candidate modules are under the private staged directory and pass syntax checks. The explicit runner accepts filenames to run the initial three tests before the expanded suites and prevents imported fixture tests from inflating counts. No candidate execution result is claimed yet.
