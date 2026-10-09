# Conditional self-cast candidates in the active audit

The 30 `Spell target is outside native range` rows in
`class-engine-active-review-20261007.json` are generated `self` scenarios at
distance zero, not casts that reached effects. They cover 15 spell references
at two levels each. The audit's candidate generator treated any conditionally
allowed self-cast rule as a scenario to try; it did not assert that the rule
was selected in the initialized fight.

The current rows show the conditions needed for those candidates are absent.
Twenty-eight rows cover Osamodas references 7307–7321 (excluding 7316); each
self-cast policy is false by default and conditionally true under
`HasState(7123, "caster")`. The tested innate-state snapshot contains 7129 and
4464, not 7123. The other two rows are reference 6986: its self-cast exception
requires `IsInFight()`, state 6364, and one of the specified levels of state
6540. The row snapshot has states 6381, 4464, and 7560, so that branch is not
selected either.

The 15 corresponding native casting records agree with the rejection. Their
baseline minimum range is above zero at every audited level. Reference 6986's
zero-range conditional tables require the same absent 6364/6540 conditions;
the Osamodas conditional tables are keyed by the absent state 7123. Thus the
selected table in these snapshots excludes distance zero, and the conditional
self exception is false. These rows are scenario-legality rejections, not
evidence of a bad conditional-table selection or range formula.

`audit_active_spells.py` now marks condition-only self candidates as
`speculative_conditional_self_candidate`. It preserves the original rejection
status and reason, and adds `legality_assessment` only when the actual selected
native casting table and self-cast policy prove that the speculative
distance-zero scenario is illegal. If that proof is unavailable, the original
failure remains unclassified. This logic uses the exported rules and live
condition context; it has no spell-ID or state-ID special cases.

Evidence hashes:

- Prior class-engine audit: `6c9cc6ee1e8672464c094b3f6b19ceef4f4332f1c510eda9b8b911c20da99b4f`
- Native casting catalog: `86aa881d5ed9231baf5000b7cdcc9326591193aca0bf31699e35c3af2a7072ff`
- Native self-cast policy catalog: `9a8222a48dcbb39051fcc603bb5efcc913774bb1609a938aa2d7c528e17ccb68`
- Canonical JSON hash of the 15 selected casting records: `1aefeee35d3d53f3c132438bf78d25d9be14e01db36acb484b9bd8e5b4066b62`

The 15 records were extracted by streaming the compressed casting catalog and
retaining only the audited references. No full catalog audit was rerun for
this review.
