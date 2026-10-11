# Lessons from automatic monster spell activation

Date: 2026-10-10. The findings below include historical inactive-candidate diagnostics. Final validation subsequently enabled 30 completely passing references; see the [deployment receipt and limits](DEPLOYMENT_20261010.md). The 39 pending candidates remain disabled.

## Reuse the existing combat engine

Native monster abilities already identify spell references and their level rule. The existing installed-client exporters can extract their effects, parameters, children, states, casting roots, conditions, costs, areas and usage limits. The generic NPC transaction already uses the same effect dispatcher and transaction machinery as class spells. A separate monster spell engine is unnecessary.

The source inventory covers 2,874 monster references and 3,091 owned spell references. The strict below-level-10 cohort contains 69 references whose entire native level range is 1–9. Its dependency export contains 111 spell references, 562 spell effects and 84 referenced states. Higher-level and epic references remain inventory-only.

## Family coverage is a screening tool

The broad static audit found 1,669 references with all required effect families implemented. This establishes useful reuse potential, not successful casts or complete encounters. Native targeting, conditions, actor registration, resources, initial states and packet serialization can still prevent execution.

The first complete native low-level audit exercised 169 actor-level/spell combinations: 129 produced effectful results, and 30 references passed every owned spell/level combination. The other 39 remained pending. Twenty-one selected references have native initial states; successful isolated spells do not establish correct initialization. A bounded target search also cannot prove that an unsuccessful conditional spell is inherently broken.

The 30 fully passing references subsequently passed native AI forecasts, serialized commits and injected serializer-failure rollback checks. Observed changes included HP, AP/MP/WP, position, states and other actor statistics. These receipts describe the tested source revision, not whichever source happens to exist later.

## Preserve previously executable shared abilities

The old NPC-specific catalog listed Wonejo spell 7962, but that list was not the complete pre-existing NPC capability set. NPC casting also compiled class, granted, captured, triggered, morph, state and area dependencies. A read-only snapshot review found 225 monster/spell pairs at their inspected minimum levels with roots already present outside the old NPC spell list, excluding 7962. Root presence alone does not prove their complete transactions succeed.

Therefore filtering native ownership to old NPC spell IDs plus newly selected monsters would regress previous capabilities. The implementation now preserves native ownership and selects between two compiled views:

| Cast | Available definitions |
| --- | --- |
| Approved monster reference, actor level and owned spell | Shared class definitions plus expanded NPC effects |
| Any other NPC cast | Shared class definitions plus the exact original NPC baseline effects |
| Player class cast | Existing player casting route |

Native temporary grants retain their ownership route. The catalog view still governs whether their effect definitions are available. The preserved baseline is copied from the pre-import document and checked against its pinned hash; it is never reconstructed from the expanded catalog. Later preparations retain that original baseline instead of treating previously imported but disabled effects as legacy.

## Version data and code together

The initial active release lacked the full native spell resource-cost authority required by the shared runtime. Offline validation initially rejected every cast correctly. The complete 4,143-spell cost export resolved that dependency; disabling cost checks would have hidden the problem.

Another workstream subsequently published exactly that cost document, moving the active revision from `a3272ec3b722c5923cdfb619041bab41a14c85d9838364440e5f71b9b2254095` to `1d428d93dd4eeea23c81d10230b33e7bfd897671930efaf8d56ac1c0e82b19f6`. The active-revision fence rejected extension of the old candidate. A fresh candidate against the new revision reproduced the 169/129/30/39 results. Only NPC effects and missing casting-root entries differ; the other 7,482 documents retain their checksums.

Concurrent changes to casting-cost selection, effect dispatch, nested cost replay and multiplayer NPC authority subsequently invalidated source stability in further receipts. These are real behavior changes, so previous successful tests cannot certify the current checkout. Diagnostic unit tests may continue while the other workstream runs; final activation requires a stable shared source snapshot and matching receipts.

## Test the actual transaction contract

Successful commit preserves existing Fight and Actor identities while adopting their prepared runtime state. A test requiring replacement object identities is incorrect. Verify observable state, serialized packets, action sequence and atomic rollback instead.

Keep separate checks for forecast source immutability, actual effectful execution, commit delivery and serializer-failure rollback. A decision to cast, a prepared animation, or an implemented family is insufficient alone.

## Treat fixtures as complete native snapshots

Stricter shared authority checks exposed old tests that omitted LOS actor heights, QI populations, actor registration, control flags and global PV producers, or moved actors and changed resources without updating their authoritative snapshots. These errors should be repaired in fixtures using native catalog values and lifecycle helpers. Production validation must remain strict, and existing behavior assertions must remain intact.

The broad class/combat run grew from 132 to 173 tests as concurrent class regression tests were added. The latest baseline and candidate diagnostic runs each passed all 173 tests without skips. The candidate's sources remained stable, but the baseline observed a concurrent change to `test_combat_event_costs.py`; the receipt comparator correctly rejected a certified comparison between different fixture hashes. Individual green results do not override that fence or replace fresh native monster execution. Intermediate failures remain diagnostic history. See [execution lessons](EXECUTION_LESSONS.md) and [class regression lessons](CLASS_REGRESSION_LESSONS.md) for scope, commands and limitations.

An additional repository-wide syntax check parsed all 2,022 Python files beneath `server/` without errors. This checks syntax only; it does not replace runtime tests or establish source stability.

The broad read-only server discovery ran 6,151 tests and reported 197 failures, 109 errors and 1,477 skips. Several failure counts include subtests under the same method; they are not independent root causes. Native catalog configuration activates additional imports and tests, so its total cannot be directly compared with a discovery run lacking the database URL. Keep environment failures, stale fixture authority, possible shared-cache ordering effects and source defects separate until investigated. See [local unit validation](LOCAL_UNIT_VALIDATION.md) for commands and observed clusters. The 82 focused offline activation/preservation tests pass, but that does not make the broad suite green.

## Remaining acceptance work

1. Finish the local/unit diagnostics and record unresolved failures.
2. Wait for the other combat workstream to finish, as Hector requested.
3. Repeat native low-level execution, AI commit/rollback and the same broad baseline/candidate class suites against stable code.
4. Finalize only completely passing references and preserve all pending inventory statuses.
5. Coordinate publication and the complete current world build with its operator, then perform the full manual acceptance sequence in [the activation report](ACTIVATION_UNDER_10.md).

No server restart, live fight commit or catalog publication was performed by this workstream.
