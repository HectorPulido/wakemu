# Native sex and lateral-facing conditions

`IsSex` is original `eOO`, using `eII.a` to require an actual `eGj`, then reading `eGj.aXz`. Its constructor accepts one or two literal strings. Only a case-insensitive `Male` maps to byte 0; every other first string maps to byte 1. The optional second string switches to target only when it equals `target`, ignoring case. Other strings retain caster selection. The evaluator returns native 0 for a match, 1 for a mismatch, and -1 for a null/non-eGj result; the Boolean criteria adapter preserves the match result.

The runtime now carries the actual sex byte through `NativeActorAuthority` and `ConditionActor`. Fresh owned PCs use their authoritative character `sex` (0 or 1); missing legacy fixture data stays unknown, and malformed values reject. Ordinary fresh NPCs use the audited `eGj.aWs` zero byte. Detached summon construction also uses `aWs` zero, while the shared descriptor stage reads `eHD.aXz`, whose original implementation returns literal zero. Captured descriptors do not inherit their owner's sex. These producers do not infer sex from breed, actor type, control, or a profile ID.

`IsSidestabbed` is original `eOP/eIG`. It shares the existing facing selection and live `Sl.o` geometry, accepting both native lateral enum results (`Sk.bor`, `Sk.bos`). Only optional string `target` switches selection; other strings select caster. Null selected eGj, null locator, non-PV opposite argument and a non-lateral result return native -1. The existing fight-property 47 locator-null guard is preserved. Explicit cells are not fabricated into opposite PVs.

The common parser validates the exact signatures before evaluation, including short-circuited branches. Conditions are wired generically; no state/spell-reference exception was added. The affected source examples are Osa states 7123/7349 (male/female references 326546/326547) and the class-14 spell 7105 lateral-facing selector.

## Offline fixture source

`audit_active_spells.fixture(..., sex=0)` now supplies an explicit male PC source, with `sex=1` available for a female variant. `audit_class_initialization` cases likewise accept `sex=1`; their ordinary offline fixture remains male. Actual accounts have no default or substituted sex. Neither tool was run as a bulk audit by this change.

## Verification

`PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_condition_sex_side test_combat_condition_facing test_combat_symbiot_condition`: 14 tests passed in 0.017 seconds. New tests cover exact string/default selection, null/nonfighter/missing-byte guards, male/female source values, detached summon construction, live lateral geometry, locator-property guards and malformed AST signatures.

`java -Xmx128m -cp '.runtime/combat-review-20261007/portal-geometry/classes:client/lib/*' ProbeNativeSexSideConditions`: original `eOO/eOP` passed 77 assertions, terminal exit 0, without a catalog or service. This covers 60 sex-byte/string/selector combinations, null eGj, and 16 live lateral/locator cases. The first probe expectation for a non-lateral result was corrected from 1 to the source-proven -1; runtime Boolean rejection was already correct.

The source pipeline is implemented and native predicate results are verified. A subsequent full Ready/dragon transformation run is still required to claim gameplay completion.
