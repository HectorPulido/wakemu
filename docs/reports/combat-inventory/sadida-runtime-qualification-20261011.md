# Sadida runtime qualification — 2026-10-11

Work in progress. PostgreSQL published catalog is authoritative. No independent restart, deployment or catalog activation is performed by this class workstream. Shared-engine edits require root coordination. Literal native `False` gates stay disabled.

## Confirmed results

- Actual native Ready plus all20 optional passive initialization subcases:2/2 methods passed. This is ownership/initialization evidence, not twenty semantic passive passes.
- Actual Semilla8137 selects a genuinely unoccupied legal cell and creates owned seed area1835.
- Actual La Vudul926 targets a character and creates profile3745 with book8140 and complete owned QI registration. Its construction cell is selected by the native constructor; the cast target is not that cell.
- Actual seed8137 followed by elemental925/921/918/932/930 creates profiles3747/3748/3749/3750/3751 with exact authoritative books and fresh owned summon slots. All five transformations passed.
- Actual seed→925 doll→next owner turn→911 creates profile3746 and its exact seven-action book. Native911 requires an existing owned doll excluding Voodoll; a fresh empty arena correctly rejects it.
- Actual seed8137→8137 recast at its cell creates tree5577 with state8217 and an authoritatively empty action book. An empty book is intentional, not a missing definition.
- Normal active audit:21/21 direct IDs inventoried;17 prepared and committed;32 individual preparations/commits; zero transaction rejections. Separate actual-context tests now qualify920/935/5057/8139; see integration results below. Three Ready grants are excluded from the21-active denominator.

Logs: `.runtime/remaining-six-refresh-20261010/sadida-final.log`, `sadida-grant-doll-death-final.log`, `sadida-doll-death-final2.log`; normal matrix `sadida-normal-matrix.json`.

## Source-corrected fixtures

Initial Semilla helper chose the first legal target, including occupied self. That is a legal recycling/no-op context, while effect378184 requires a free cell or the authored seed/passive8150 branch. Initial seed creation now selects an actual unoccupied cell. No runtime eligibility guard was weakened.

The first Superpoderosa fixture had no existing owned doll; native criterion requires one. The corrected acquisition sequence builds that prerequisite through actual casts and a real turn boundary.

The seed transformation fixture initially asserted that every native area count equals1. Some deck contexts legitimately create another innate area. It now identifies the actual1835 seed by reference and retains other areas unchanged.

Action8138 requires Sadida Solitario912 on the original controller. Its positive scenario now equips that passive before Ready. Actions5025/5356 require real recipients; an empty legal casting cell can produce no enabled effect. Their fixture now places a real enemy in an unobstructed native range, rather than accepting a no-op receipt.

The Voodoll KO test first confused the926 character target with a summon placement target and then assumed its naturally selected cell was adjacent to the NPC. The current probe advances the actual NPC turn and performs certified native movement before the real7962 attack. It does not teleport a registered actor or inject death notifications.

## Pending terminal scenarios

Remaining actual doll action dependencies8138/5356; Superpoderosa5153 and Voodoll8140; multiowner isolation, cap/replacement, secondary state/area lifecycle, second-fight/reconnect and complete passive semantic controls. Completed KO/revival/armor/920/935 paths are recorded below.

No full provisional-ready claim is made yet.

## Additional actual integration results (2026-10-11)

The frozen five-method run in `.runtime/remaining-six-refresh-20261010/sadida-actions-death-remaining-final.log` confirms three additional integration paths:

- Voodoll death through an actual NPC spell releases its native QI slot while leaving its owner alive. The NPC uses its certified movement path before attacking; the fixture does not teleport actors or manufacture a retirement event.
- Zarza cast on the Sadida produces real armor, which satisfies Fuerza de la Naturaleza's armor prerequisite and installs state 8224.
- Despertar Silvestre (5057) restores an allied character after an actual NPC knockout, with full multiplayer authority supplied to the transaction.

The remaining doll-action investigations concern 5356 target prerequisites and action 8138. For 8138, a native eligible candidate reaches `Unsupported native state level`; root 378019 is family 844 and references state 8209 (native maximum level 5). This is an integration failure under investigation, not a missing definition claim. The focused rerun now exposes its complete exception stack instead of conflating it with rejected search candidates.

A separate test module, `test_sadida_super_voodoll_actions_pipeline.py`, adds semantic assertions for Superpoderosa 5153 enemy damage and Voodoll 8140 swapping with an owned doll. These assertions are pending execution and must not be counted as qualified behavior.

The subsequent frozen run `sadida-actions-death-remaining-final2.log` also passes Sacrificio Muñequero (920) and Terremoto (935), using an actual owned doll prerequisite. Sacrificio's native range-zero cast targets its owner and retires the owned doll; targeting the doll was an invalid fixture assumption. Together with the 17 direct baseline contexts, the four previously unresolved active contexts (920, 935, 5057, 8139) now have successful actual native casts. This qualifies cast execution, not every branch of all 21 actives.

The same run isolates 5356 more precisely: the adjacent owner cell passes range and LOS, then rejects its native `HasState(8190)` prerequisite. State 8190 has actual transformation producers 378061 and 378069. Its absence after the tested Bloqueadora creation remains a lifecycle investigation; no guard is bypassed.

`test_sadida_super_voodoll_actions_pipeline` is not green: Superpoderosa's selected enemy cell rejects LOS (`twU`). Its Voodoll scenario fails earlier than 8140, during a subsequent Zarza seed transformation after Voodoll creation, with `Unregistered non-null native criterion recipient`. Consequently neither new action is claimed as qualified. `probe_sadida_dependency_failures.py` instruments the unchanged native failure path to identify the exact effect and recipient; it does not supply synthetic authority or skip criteria.

## Narrow shared correction under validation

The dependency probe identifies the 8138 exception precisely: effect 378022 computes state parameters `[3624, -1, -1]` at container level zero, while its native criterion requires container level at least two. Native eWu calculation stores a signed short before criteria evaluation; rejecting that intermediate calculation prematurely aborted the cast. The correction allows signed levels **only during preparation**. Application retains the existing negative-level rejection, and dispatcher order is unchanged. The focused regression module tests signed calculation, false-criterion skipping, and atomic rejection when a negative application actually qualifies. Actual 8138 and shared state regressions are pending terminal validation.

5356 was a source-context mismatch rather than a proven missing state route: native spell 930's roots do not reach the Enganchadora state 8190, while spell 934's roots 378057/378065 do reach producers 378061/378069. Both variants use profile 3751. The action fixture now creates its actual 934 variant and preserves the state prerequisite. This corrected scenario is pending execution.

The Voodoll/seed sequence fails at effect 377823, caster 7, target 70 (the selected seed-area identity), before the intended 8140 action. Investigation concerns the lifetime of an actual selected area PV across ordered siblings after Qs unregistration. Unknown recipients must continue to reject; no permanent fake area or null-recipient fallback is authorized by this finding.

## Actual selected PV lifetime correction under validation

An ordered native group holds its selected PV object while its children execute. Unregistering that area's Qs membership does not turn the already selected object into an unknown recipient for later siblings. The shared correction now scopes the validated selected caster/target area rows to ordered-group execution, releasing them on both normal completion and exceptions. It does not restore spatial membership or persist a new retired-area entry.

Direct identity predicates (`IsSpecificArea`, `IsAreaType`, and owned-area identity) can resolve that actual selected object inside the scope. Cell scans and spatial predicates still enumerate only registered active areas. Unknown identities continue to reject. This distinction is covered by focused scope tests; real Voodoll/seed and shared regression gates remain pending.

The corrected native action matrix, including actual 8138 and spell-934-derived 5356, passed in `sadida-actions-signed-final.log`. The initially added signed-calculation unit fixture used the wrong fight owner; its owner field was corrected before the final rerun. That earlier fixture error is not a production failure.

The post-correction focused batch `sadida-final-scope-actions-final.log` ran 17 methods: 16 passed and one failed. Passed: four selected-PV scope tests, three signed-calculation tests, four state-runner tests, two null-area-Qf tests, the full actual doll-action matrix (including 8138/5356), Superpoderosa 5153's actual enemy damage, and independent second-fight book/QI isolation. The remaining Voodoll→seed→Zarza integration still reports an unregistered non-null criterion recipient; the scope correction is therefore not represented as closing that scenario. A fresh bounded diagnostic is queued after the shared regression gate to identify the remaining reference.
