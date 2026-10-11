# Flag8 native health comparator prototype

This change includes a pure comparator, a separate native identity export, and narrowly qualified offline source integration. The active PostgreSQL registry remains unchanged. Group registration accepts8 only with an exact native definition identity/contract; legacy flags-only[8,26] and unknown metadata remain rejected. Existing distance ordering is preserved.

Installed faK selects faI for flag8 before flag25 and distance14/26. faI.c queries actual PV.a(ffw.sgC) first: absent left returns1 immediately (including both absent); absent right returns-1. Present operands read PA.aYS/current and PA.aYU/maximum, convert each integer to float32, divide and multiply100 with float32 rounding, then compare boxed floats through Float.compareTo. This preserves Java NaN greater than infinity, signed zero distinction and rounded equal ratios. It does not use scalar actor.hp/max_hp fallback.

New `combat_target_health_ordering.py` accepts explicit typed native characteristic operands only. It performs no actor/container lookup and cannot establish PA presence itself. Missing presence or current/maximum operands fail closed. The caller must supply authenticated PV.a/PA evidence before integration; an absent dictionary key is not evidence of a missing native characteristic.

Native differential probe `ProbeNativeHealthTargetOrdering.java` invokes the actual installed faI with PV proxies whose sole characteristic queries return explicitly present/absent PA containers. The concrete PA subclass supplies native current/maximum operands.256 pairwise cases cover missing PA, equal ratios, large int rounding, negative values, zero maxima, NaN/infinities and signed zeros. All256 comparisons match Python. Four additional new unit tests pass without PostgreSQL; old tests were not edited.

`ExportNativeHealthTargetOrdering.java` extracts a separate flag8 identity artifact including exact definition class/flags/signed target cap and an explicit faI contract marker. It does not publish or merge the active registry. The integration requires this marker so legacy metadata cannot silently enable flag8.

Actor authority is deliberately bounded to actual registered-or-detached identity plus verified fresh native_hp_on_operand or copied PA provenance. `hp_raw_present` alone is insufficient: hp_raw_current must verify the full source/current consistency before group_pa reads effective values. Raw HP is not the comparator operand (faI uses effective PA.aYS). Unsupported actor construction sources fail closed. Areas use the separate authenticated group_pa authority, preserving proven absence; no ordinary actor fallback is used.

Private evidence: `.runtime/monster-blocker-recovery-20261011/health-ordering/` holds actual faI bytecode,256 native outcomes, differential receipt with client JAR/source hashes, and a separate extracted native flag8 identity artifact. No service operations, PostgreSQL writes, runtime activation or monster-readiness claims.

## Qualified offline integration

`health_operand_for_pv` resolves the actual registered/detached actor, rejects aliases, and requires existing fresh HP.on or copied-PA source verification through hp_raw_current. This establishes present sgC PA from actual construction, while the comparator reads effective current/maximum through group_pa. Unknown constructor/container authority never becomes scalar HP fallback. Actor effective HP must match the PA current.

Area targets must be the existing immutable NativeAreaTarget and resolve to the registered native area PV with identical ID/cell. group_pa supplies source-proven HP PA or source-proven absence for the audited concrete area class; unsupported area containers raise. No new area characteristic default was introduced.

The common resolver receives this actual-preview provider from NativeEffectRuntimeFactory. `order_native_targets` requires a separate native-health-target-ordering.json row with exact effect class/full flags/signed target cap and faI contract marker. This document is exported offline but remains unpublished; missing catalog authority still blocks execution. Group flag validation and its four callers use the same identity validator, with legacy flags-only8 rejection preserved.

An additional actual installed faH/faK probe validates72 sort/cap cases with rotated candidates, equal percentages, absent PA, NaN, infinity, and flags8/8+26/8+25. All72 match Python. Native8 priority over25/26 is preserved. Four new integration tests cover actual fresh HP operand installation, sorting before cap, old metadata rejection, unknown source, actor alias and current mismatch. Independent focused gate is pending at this document update.

## Reproducible append-only candidate packaging

Run `python3 server/tools/export_monster_health_target_ordering.py --output .runtime/monster-blocker-recovery-20261011/health-ordering/native-health-target-ordering.json`. This compiles/runs the installed native exporter, checks source hashes remain unchanged, validates all55 native rows, and writes a sibling `.receipt.json` binding the artifact digest/count to the installed JAR and exporter source.

Pass `--health-target-ordering .runtime/monster-blocker-recovery-20261011/health-ordering/native-health-target-ordering.json` to `prepare_monster_spell_activation.py`. The preparation helper validates the receipt, exact row references/classes/full flags/contract and signed caps. It adds the document only when absent. An existing identical shared digest is retained; any different shared digest fails rather than replacing concurrent work. This option does not publish or activate the candidate. The existing zero-level dependency handling remains intact.

Two new pure packaging tests pass: append/identical/conflict/source-change behavior and malformed identity/flags/contract/cap rejection. Scope-confirmed refs5446 Enca and5451 Sapo Enca (levels68–71, owned7822/7828) were added to the affected-reference replay queue. They remain pending full native execution and AI qualification.
