# Full regression expansion — 2026-10-10

## Scope and evidence rules

The earlier class delivery used focused gates, not complete repository discovery. At the user's request, validation expanded to every discovered `test_*.py` under `server/tests` and `server/ai-service/tests` (1,117 files at inventory time), including native class opt-in tests. Manual client acceptance remains distinct from automated coverage.

The user explicitly excluded investigation or modification of NPC failures because another agent owns them. Record their outcomes separately; do not change NPC spell definitions, publication or assertions to obtain a green class report.

Catalog authority is the current PostgreSQL release. Gameplay catalog reads are read-only. Write integration cases use the separately verified `wakemu_migration_test` database and per-test isolated schemas, not the gameplay database. Administration/guild/shop opt-in flags must be exercised separately if omitted in the initial discovery.

Raw evidence is private under `.runtime/full-regression-20261010/`: command runner, complete logs and source hashes. Counts from progress output are provisional and include subtests; terminal unittest counts and exact failures supersede them.

## Findings under qualification

- Aniripsa upgraded Cunejo exposed a real general turn-end transition problem: a pre-end callback can retire the current actor and advance the fight before the caller attempts to end the old actor again. A narrowly guarded reuse of the existing defeated-turn synchronization is prepared for both controlled/server turn paths. Focused ACK, single-advance and rollback tests must pass before deployment.
- The non-upgraded dark Cunejo scenario also requires tracing transformation/recreation and the identity actually killed; an observed zero HP on a retired original must not be assumed to be the death of its live replacement.
- Several production-handler tests use `/app/local_game_server.py`, absent from the documented local execution environment. Such collection/path failures must be distinguished from changed gameplay; preserve their AST/behavior assertions when making the runner portable.
- Previously green isolated turn cases failed during broad discovery. Repeat exact cases in fresh processes before attributing failures to production or test-order state contamination.

The broad discovery began before the prepared turn-end correction. It is baseline evidence, not a claim that all cases tested the final changed source. Recheck affected modules after the source freeze and record pre/post hashes. No global regression-free claim is justified while failures remain unclassified.

## Completed discovery and current-source follow-up

- Server discovery: 6,368 tests in 3,248.783 seconds; 214 failures, 64 errors, 66 skips. The source manifest changed during execution; these results are a mixed-source baseline.
- AI discovery: 583 tests in 62.726 seconds; one failure, two errors, no skips. The forecast randomness import error passed with the required `server/tools` import path. The NPC AP expectation is excluded from this agent's investigation.
- Fresh shared turn/recovery/LOS bundle: 51 tests, 48 passed, two failures and one error. The pre-end death, runtime messages, defeated-turn ACK, multiowner, turn event, disconnect and recovery cases passed. Remaining LOS cases are being qualified against the current topology authority.
- Build-capacity handler tests now resolve production source relative to their own checkout rather than requiring `/app`; AST and behavior assertions remain intact. Fresh execution is pending.

NPC failures remain recorded in the raw log and assigned to the other agent. Opt-in isolated database tests and final class follow-ups are still pending; this report does not certify global regression freedom.

## Subsequent qualification

- Build capacity: 25/25 passed against the isolated database after the portable source-path correction.
- Casting and LOS: 23/23 passed after updating fixtures to supply actual conditional authority and full native topology. These corrections did not change production LOS behavior.
- Movement target diversity: 3/3 passed after replacing the incomplete graph stub with a valid NativeGraph; route assertions were preserved.
- Heart Blood: 3/3; original controller areas: 4/4; wall areas: 9/9 passed after source-qualified fixture updates.
- Isolated opt-in administration/guild/shop follow-up: 55 tests, 54 passed, one guild fixture error (`Missing account haven bag`). No gameplay database writes.
- Aniripsa: the positive actual-death area method passed all profile subcases; the separate protected-expiry negative passed. The legal fixture no longer inflates the summon's HP beyond the tested lethal action. Protected withdrawal remains distinct from normal death.
- Copied-class book completeness is a real catalog gap: eight shared passive metadata rows are absent from active revision `13c8122abba26ca40757c48df137540a5f0e6defdc6676cde6fd19ac6b84b33d`. Full revision `43ede6f86340a57ad3acd32a15ad48b892ff1a526a64ebc7c8937518e9bdac07` is staged and complete, with only the copy-flags document changed (813 to 821 rows). Its pinned runtime-book suite passed 5/5, including full universal-passive metadata coverage. It is not activated. Before rollout, recheck the active base revision and rebuild/validate the complete shared checkout; never replace concurrent catalog changes with this older base.
- Live world was independently redeployed as `wakemu-world:fishing-20261010` and is healthy. Its RuntimeMessages SHA256 matches the prepared pre-end correction (`43d482e24285ed5a70e68c6d7368fce74938ffbbdbaf15a3fb2a9254fd316ccd`). This is file equality evidence, not proof that every current checkout file is deployed.

A subsequent complete Python comparison found 647 local files versus 646 live
files, with seven different paths, including shared state/summon initialization.
The private proof is `live-world-source-proof.json`. Concurrent changes are
therefore still present; do not describe the live server as the complete tested
checkout or activate the staged catalog as though source/publication were frozen.

## Final focused gate

The combined current-source gate passed **91/91**, with zero failures, errors or
skips, against full revision
`13c8122abba26ca40757c48df137540a5f0e6defdc6676cde6fd19ac6b84b33d`.
It covers pre-end death/runtime messages, defeated and multiowner ACKs, turns,
disconnect/shared-idle, recovery, casting/facing/LOS, all Aniripsa test methods,
Heart Blood, original controller areas and wall areas. The 30 selected source
and test file hashes were unchanged before/after this gate.
AI movement passed separately **3/3**. Staged copied-book coverage remains a
separate **5/5** result on `43ede6...`; it is not a live activation claim.

Raw logs: `final-current-bundle.log`, `final-ai-movement.log`, and
`final-focused-before.sha256`/`final-focused-after.sha256` under the private
evidence directory. The complete repository discovery still has unresolved
failures outside this focused gate. The clock-summon full-area scenario requires
source-valid terrain and the actual area event before expecting its conditional
center; its original initial-cast area count is not qualified.
