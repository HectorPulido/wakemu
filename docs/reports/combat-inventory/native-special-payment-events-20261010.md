# Native special payment event audit

The original `eWf.bbx()` publishes AP event2234 only when `mi(true)` and the signed-byte AP cost is positive. The same switch qualifies MP2188 and WP2263. Fresh construction and reset set both `mi` and `mh` false. The setter only changes a field: callers must subsequently rebuild the event bitset with `bbx()`.

A complete original-client invocation scan found no `mi(Z)V` caller. The recovered static payment-factory caller is `eXm.c` (family923); it binds the actual caster and executes payment, but never enables either special switch. Generic effect-driven resource drains therefore do not prove special paid-spell semantics.

The pinned PostgreSQL revision contains 34 effects subscribing to2234; the companion JSON lists every reference. Consumers include Sram410579/410580 and multiple other mechanics. Some require triggering-caster equality, cast-end1025 cleanup, elemental activation or spell exclusions. The current synthetic payment source has null PK/PL and absent spell context. Enabling the bit alone cannot certify those additional conditions.

A defensible implementation is an explicit Wakemu paid-ability policy: qualify normal and paid nested spell receipts, enable `mi`, rebuild the native event bitset, and replay the original post phases exactly once before spell roots. Preserve generic923 drains and `mh=false`. This is the implemented explicit server caller policy, **not a recovered original server call site**. Spell-context consumers still require separately qualified context before claiming functional coverage.

Source evidence: `/tmp/sacro-eWf-javap.txt`; `.runtime/combat-review-20261010/eXm-special-payment-source.txt`; `.runtime/combat-review-20261010/eYt-special-payment-source.txt`. Private runtime evidence is intentionally outside tracked documentation.

## Implemented paid-ability boundary

The trusted normal/paid426 receipt now carries a typed `PaidAbilityPolicy` and enables the native mi-derived event set. Native event validation requires the receipt payer, source caster and target to agree. Payment is not repeated. Generic923 remains unchanged; mh stays false. The policy preserves absent PK/PL instead of manufacturing native spell or elemental context. Four focused payment tests pass; real Sram and cross-class acceptance remain pending.

Current-activation qualification: `combat_activation_conditions.current_activation` implements `IsActivatedBySpell`/`IsActivatedByElement` from the actual scoped activation and PostgreSQL `native-spell-activation` metadata. Both normal and paid426 receipts run inside that existing scope. These predicates therefore do not require inventing PK/PL on eWf. Conditions that specifically query triggering-runner PK/PL still retain their honest absent-source behavior. Paid426 now invokes the same receipt producer beside its existing Breeze receipt; zero-cost ignored casts publish no special positive-cost identifiers.

Actual cross-class acceptance passed on pinned revision347: `test_combat_hud_producers.NativeHudProducerTests.test_ouginak_manada_form_lifecycle_uses_native_resource_and_removes_visual`. Native Manada7551 generates20 resource117, legitimate granted6855 enters state7526, and6288 activates elemental listener339923 through the paid receipt. The existing resource-zero, form-exit and visual-removal assertions also pass. Evidence: `.runtime/three-class-review-20261010/current-class-focused-rev3472.log`. This does not certify every2234 consumer.
