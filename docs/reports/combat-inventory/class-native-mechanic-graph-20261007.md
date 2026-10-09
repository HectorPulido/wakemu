# Native typed class-mechanic graph — 2026-10-07

The original installed client now supplies a richer class-only dependency graph than the earlier compact structural snapshot. It begins with **813 class definitions (722 class spells plus 91 extras), 22 native innate states and 39 class-referenced profiles**. The profiles expose 43 abilities, including 38 additional trees, so there are **851 seeded spell definitions**. General monster spells and AI execution remain outside scope.

The final export contains **851 spell nodes, 764 state nodes, 90 area nodes, 21,207 effect nodes and 39 profile nodes**, with **58,729 typed edges**. Three state definitions are natively absent: 759, 7986 and 8873. Their historical native false guards are retained; missing structural nodes do not establish a reachable gameplay failure.

[Typed graph JSON.gz](class-native-mechanic-graph-20261007.json), [compact summary](class-native-mechanic-graph-20261007.summary.json), [18-class component matrix](class-native-mechanic-components-20261007.csv), [area contracts](class-native-area-contracts-20261007.csv), and [target selector contracts](class-native-target-selector-contracts-20261007.csv) are reviewable outputs. The [combined gap index](class-mechanic-gap-index-20261007.md) links state, condition and shared runtime evidence.

## Exported authority and expectations

Each effect preserves its complete original criterion text and actual parsed native object structure, native runner class, native target selector, seven distinct definition-mask channels, effect flags, HMI trigger records, timing data, subscription ownership, priority and execution count. HMI triggers are not relabeled as combat event producers. Raw escaped criterion line breaks remain verbatim; parser normalization is explicit in the condition inventory.

Actual native parameter, probability and timing evaluations cover levels 0–245 and relevant signed-short boundaries. Spell root selection and state-selected roots retain native ordering and exact sampled levels, including zero. These are expectations for the sampled primitives; they do not assert that those levels are legal casts or that a guarded runner executes. Full native evaluation rows are private in `.runtime/combat-review-20261007/mechanic-graph/native-graph.jsonl.gz`; public nodes reference their exact evidence line and hash.

Typed reference edges use proved parameter contracts: state304 slot0, configured native eYQ area runners including314/315/339 slot0, grant649 slot2, and summon307 slot0. Boundary-only and negative observations stay explicit; positive references are traversed through the 0–245 sample domain. Other reference producers, transformations, context overrides and references embedded in criteria remain unclassified until their native contracts are proved. No arbitrary runner C or criterion was executed by this export.

The graph preserves group/root order and reverse indices. Class components separate spell dependencies from common native innates, including cosmetic/KO branches. Dependency edges do not automatically mean execution: grant, area and profile links describe additional definitions, and native masks/condition classes describe stored metadata. Every dynamic reachability claim remains unknown.

## Integrity and persisted catalog comparison

The final export snapshots mutable native loader records before retaining them. All **761 present state identities and 90 area identities** were independently checked against their requested references, preventing callback object reuse from corrupting the inventory. The exporter also asserts those identities itself. Intermediate exports with an incorrect grant slot or reused loader records were rejected and retained privately as invalid; the public final graph uses the corrected export.

All **243 tracked native sources and inputs** remained stable. Graph indexing publishes atomically. [Persisted catalog comparison](class-native-catalog-comparison-20261007.json) then checks all 21,207 effects against class, granted, state and area sources plus the actual native point-area metadata join:

- No missing effect definitions, numerical differences, criterion differences, selector/mask differences or timing-field differences.
- All 21,207 available compared definitions match the native export after the actual point metadata join.
- 461 tree rows omit point offsets but receive them from the existing `merge_native_point_areas` producer. They are not missing runtime definitions and no redundant catalog rewrite was performed.
- 466 duplicate source records differ only in native-equal additional timing evidence, point fields supplied by that join, or allocated HMI IDs.
- 554 HMI records differ only in their allocated ID, including that same ID in native OY.toString. Normalization leaves every other exported trigger field unchanged; persisted IDs were not rewritten.
- Shorter stored parameter sample domains are separately reported. Matching the available samples does not attest all extension domains or context-derived runner values.

Definition equality does not prove the consumer implements the definition or the client applies its delivery.

## Concrete gaps beyond family registration

The native area matrix contains 64 GLYPH, 13 HOUR, four ENUTROF_DEPOSIT, four AURA, three FAKE_FIGHTER, one GATE and one WALL prototypes. ENUTROF_DEPOSIT and WALL have no audited creation-type branch in the current area handler. Other type branches are conditional implementations whose complete statistics, owner, occupancy, activation/removal and expiry domains remain unknown.

There are 108 distinct native selector contracts. Current source recognizes 105 fcE masks; three mask patterns require unsupported bits44/46 across six effect definitions. A recognized flag mask still requires actual actor/PV facts and complete target semantics. Seven definition masks remain separate from fcE flags.

The condition inventory distinguishes 116 textual function calls, 115 exact original-parser name mappings and 130 parsed structural classes, including operators and literals. These are not 130 predicate implementations. The state inventory distinguishes shared route gaps from pending per-state lifecycle verification. Neither inventory turns source presence, Ready cycles, scenarios or native export rows into complete class mechanics.
