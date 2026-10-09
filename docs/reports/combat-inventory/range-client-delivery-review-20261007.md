# Range client/server delivery review — 2026-10-07

The earlier range review identified a real common server omission: ordinary casts bypassed conditional casting tables, and exported tables lacked the modifiable-range flag. The current source corrects both: all casts select the complete native fyP and resolve live RANGE/category modifiers through combat_casting_range. This review does not establish that this source is loaded by the user's running server or that packets reached the client.

## Shared contract and current coverage

All 813 ledger spell IDs have casting definitions. Of these, 212 baseline tables permit RANGE modification; 286 have conditional tables containing 651 branches. Baseline and conditional range flags are present throughout. This is catalog coverage, not execution certification. The installed client derives ranges from its native spell tables and live actor facts; there is no separate per-spell effective-range packet in this inspected delivery path.

Native `fyF` selects the entire conditional table, adds per-category `eHl.pOK` modifiers to maximum, and `fcj` applies characteristic `ffw.sgK` (11, RANGE), the carried increment, minimum clamp and property2 cap. The current server uses the selected minimum/maximum/flag/categories and the live snapshot. Conditional selection can still explicitly reject unknown authority or ambiguous unequal matches.

General RANGE is carried in the actor characteristic snapshot (`tB`: byte PC identity plus current/minimum/maximum/percentage integers). snapshot_characteristics serializes all registered snapshot IDs, including11; the runtime adapter reads the same live effect_stats into ConditionActor characteristics. Readiness captures the baseline BEFORE innate effects and sends effect applications afterwards, preserving native ordering. Turn/recovery snapshots update current characteristics.

Category modifiers are a separate contract. Native1066 is `eZg`; applying adds its amount to `eHl.pOK`, removal adds the negated amount. Its inherited eZf serialization stores category in AdditionalDatas `ij.getValue`; native ij.writeTo writes this as protobuf int32 field10. The current handler emits category field10 inside running-effect AdditionalDatas field8, applies the same amount to spell_range_modifiers, and emits owned application13497/removal13560. Characteristic snapshots alone cannot reconstruct this category map. AP1065 uses a separate map and opposite sign.

## Remaining evidence gaps, ordered

1. Verify loaded runtime/catalog freshness against the corrected source and native range-flag export. A stale server reproduces the earlier cross-class mismatch even when the checkout is fixed. No service inspection was performed here.
2. Verify actual application/removal delivery and native client execution for RANGE-changing innates/passives and category1066. Server mapping mutation or emitted bytes alone does not prove reception. Missing/rejected application can leave the client's category map different from the server; a later characteristic snapshot will not repair it.
3. Verify the client's deck/states and the server's authoritative casting context agree when selecting conditional tables. Current source preserves unknowns instead of choosing a guessed range. The full-game acceptance should compare displayed range, a boundary cast, state/deck changes, and expiration/removal using the same actor snapshot.
4. Recovery reannounces timeline and current characteristics but does not replay/reconstruct category1066 modifiers in this inspected path. Existing client state may be retained; cold reconstruction/resynchronization of eHl modifiers is not accredited. Do not send an empty running-effects snapshot over a live actor as a substitute.

No current source-only proof identifies an additional Ocra-specific range bug. The confirmed fix is shared across classes; actual UI agreement remains an end-to-end delivery check.

## Offline proof and checks

Native bytecode inspected: eZg, eZf, eHl, ij; original fcj oracle is exercised by existing casting-range tests. Command: `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python -m unittest test_combat_casting_range test_combat_spell_cost_effect test_casting_range_flag_merge`. Result:13 tests PASS. No services, database or client interaction.

Source hashes at review time (no complete pre/post execution manifest claimed):

- `server/wakfu_server/combat/combat_cast.py`: `7d43cf6d2050d533cfce7fa95c84c8f27c10e575c151a462c605dee5ed392b22`
- `server/wakfu_server/combat/combat_native_spell_casting.py`: `6408913774c7e0a0836e0525ef0dd7a296ef4b647d8db4e4c1a85560ed0198b4`
- `server/wakfu_server/combat/combat_casting_range.py`: `81f3b9e88f40b9bec70b5f81966b8f8f1e6a8ac251cb232c44cc2f4fefcce487`
- `server/wakfu_server/combat/combat_spell_cost_effect.py`: `0d22175e038a242f98a9091fa600585e12e126234d35b3d13481c2171283ce8c`
- `server/wakfu_server/combat/combat_snapshot_wire.py`: `e03e87414a5463797beae8cf14e2beaed9d61ee32ed6e916bf570e529eb4a082`
- `server/wakfu_server/combat/combat_ready.py`: `3b84af790a908152d5453104c37a3f6512ef6a3d023bcd3fb3e36e08ef8ec757`
- `server/wakfu_server/combat/combat_runtime_messages.py`: `02f38c48a45aa8cb9c671d522d3800cd2872f35a9fb6aebc724b56eb4352c3c7`
- `server/protocol/native-spell-casting.json`: `86aa881d5ed9231baf5000b7cdcc9326591193aca0bf31699e35c3af2a7072ff`
- `client/lib/wakfu-client.jar`: `e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd`
