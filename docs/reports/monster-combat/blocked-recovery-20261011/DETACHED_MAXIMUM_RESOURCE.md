# Detached maximum resource constructor recovery

Representative selected by the recovery coordinator: monster2658 (Guawdia wabbit seco), among24 records previously blocked by `Invalid native maximum resource actors/fight`. This count is a historical error cluster, not a verified recovered count.

Native initialization evidence already encoded in `combat_npc_initialization.py`: `big.a(eGH)` consumes descriptor `cle` initial-state triples before controller/team/QI registration. The state caster and target are the actual detached SELF actor. Requiring roster membership and active phase at this boundary prevented eWN maximum-resource effects even though their implementation already existed.

The fix reuses `registered_or_detached_actor` and `constructor_stat_context`. Only an actual fight-scoped detached SELF constructor can bypass active registered-fight requirements. Other casts still require both actors registered and active phase. Source guard verification, parameter parsing, native resource snapshot checks, caps, raw/current semantics, ownership and delivery are unchanged. Application mutates the actual constructor actor without adding aliases to the roster. Maximum-resource removal resolves that same actor during synchronous constructor rollback.

All roster accesses in the file were audited. Initial audit retained eWO/eZI entry restrictions until actual replay identified eZI constructor failures for2829 Skalo,2867,3081,3084 and4453. Follow-up native bytecode confirms eZI.c and eWO.c consume target PV/PA directly without active-turn or roster requirements. Both now reuse the identical actual detached SELF guard; eZI still rejects dead actors. Their removals resolve the genuinely scoped actor, preserving reversal symmetry.

## Focused verification

Command: `.runtime/local/verification-venv/bin/python .runtime/monster-blocked-recovery-20261011/run_maximum_tests.py`.

Result:26 tests passed (6 new regressions plus20 existing maximum/reduction/percentage tests),0 failures/errors. Catalog reads were PostgreSQL read-only; Redis writes disabled. Existing test files and assertions were untouched. New regressions cover real detached SELF mutation and removal, no roster insertion, absent scope, cross-actor targeting, registered-caster-to-detached-target rejection even in active phase, source guards, and registered placement rejection.

An initial new fixture used canonical and compatibility module namespaces together, producing different authority class identities; the new fixture was corrected to consistently use the existing compatibility imports. Production authority validation remained unchanged. A plain shell test invocation initially lacked catalog environment; the read-only runner supplies it.

No services, images, deployment, activation policy or database content changed. Actual representative and cluster replay belongs to the coordinator's subsequent offline recovery pass; this report does not claim24 recovered monsters. Heavy full-matrix validation is deferred to the final pass.

## Changed implementation/test SHA256

- `server/wakfu_server/combat/combat_maximum_resource.py`: `4f5aa7788c2168daac080fa462056145901db85535f313532d195a73e0558b29`
- `server/tests/test_combat_maximum_detached_constructor.py`: `7a39c326cdbec6c0d9cf73a256eb5efccccaa212ed4f021cb855a3d71f71bed3`

## Follow-up percentage/reduction recovery

Representative2829 Skalo progressed past prior barriers to the percentage-HP actor/fight gate in the coordinator cheap batch. Source inspection was read-only: `eZI.javap` and `eWO.javap` under the runtime evidence directory show direct PV/PA operations; they impose no registration or active-phase requirement. Entry guards now use the exact same constructor predicate as eWN, preserving registered active requirements otherwise.

Seven additional new regressions verify eZI maximum percentage application/removal with explicit current flags disabled, eWO reduction/application removal, missing constructor scope, cross-target, foreign caster in an active fight, unverified guards, and dead percentage actor rejection. A first new fixture assumed positive percentage restore would reverse current symmetrically; native eZI.bbR instead applies its signed PA.oo reduction. That expectation was discarded in favor of explicit current flags; existing native arithmetic was not altered. Existing percentage tests continue to verify their established current/death semantics.

Final combined focused result:42 tests passed,0 failures/errors, including19 new tests across both new modules. Existing test files remain untouched. Actual recovery counts require the coordinator replay; no new activation is claimed here.
