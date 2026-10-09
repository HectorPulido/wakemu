# Combined class mechanic and gap index — 2026-10-07

The reviewable denominator is **722 class spells plus 91 extras across 18 classes**. The scoped native graph also follows43 class-summon abilities, including38 additional trees, for851 seeded spell definitions. This index maps definitions and dependencies; complete dynamic class semantics and manual client acceptance remain **unknown**.

| Dimension | Current evidence | Remaining distinction |
| --- | --- | --- |
| Native typed graph | 21,207 effects;764 states;90 areas;58,729 typed edges | Structural/sampled authority, not guarded execution |
| State lifecycle | 79 partial;682 pending verification;3 absent | Installation, stacking, duration, expiry, retained children, decurse and reconnect tracked per state |
| Condition contracts | 116 textual calls:98 partial,18 absent;130 native structures | Operators/literals included; parser/signatures and runtime producers tracked separately |
| Shared effect routes excluding creature creation/control | 145/177 registered (81.9%) | Source registration only; not percent working spells or complete mechanics |
| Area type branches | 85 prototypes have a conditional type branch;5 lack an audited branch | Missing ENUTROF_DEPOSIT/WALL; supported types still need full lifecycle/context |
| Native target selectors | 108 recognized fcE masks;0 unsupported patterns | Bits44/46:18 unit tests and20 native oracle cases; actor/PV providers remain separate |
| Persisted effect data | All 21,207 compared definitions native-equal after actual metadata joins | Context-derived values and broader sample domains remain unproved |

## Whole 18-class component matrix

The following states/areas/profiles are transitive dependencies from each class spell/extras seed. Innates are recorded separately in the JSON so common cosmetic and KO ancestry does not masquerade as a class-specific mechanic. Counts overlap between classes and are not completed mechanic counts. Spell labels and exact state, area, profile, condition and effect identities are preserved in the machine data.

| Native class | Class spells | Extras | Spell-dependent states | Innate-dependent states | Spell-dependent areas | Profiles |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| FECA | 39 | 2 | 61 | 7 | 9 | 0 |
| OSAMODAS | 38 | 8 | 33 | 20 | 4 | 2 |
| ENUTROF | 38 | 4 | 39 | 41 | 8 | 5 |
| SRAM | 36 | 9 | 24 | 18 | 3 | 1 |
| XELOR | 41 | 3 | 40 | 17 | 24 | 4 |
| ECAFLIP | 41 | 16 | 70 | 53 | 1 | 3 |
| ENIRIPSA | 41 | 3 | 38 | 22 | 2 | 4 |
| IOP | 41 | 4 | 51 | 28 | 3 | 1 |
| CRA | 40 | 6 | 33 | 22 | 1 | 3 |
| SADIDA | 41 | 3 | 68 | 53 | 9 | 8 |
| SACRIER | 41 | 5 | 40 | 28 | 1 | 0 |
| PANDAWA | 38 | 5 | 39 | 16 | 1 | 1 |
| ROUBLARD | 41 | 4 | 64 | 47 | 7 | 4 |
| ZOBAL | 40 | 5 | 41 | 16 | 2 | 0 |
| OUGINAK | 40 | 4 | 32 | 21 | 3 | 1 |
| STEAMER | 41 | 4 | 31 | 12 | 4 | 2 |
| ELIOTROPE | 41 | 3 | 31 | 18 | 12 | 0 |
| HUPPERMAGE | 44 | 3 | 42 | 41 | 6 | 0 |

## Reviewable files

- [Complete typed native graph and provenance](class-native-mechanic-graph-20261007.md).
- [18-class components JSON.gz](class-native-mechanic-components-20261007.json) and [CSV](class-native-mechanic-components-20261007.csv), separating spell and innate closures.
- [Every state and lifecycle contract](class-state-gap-inventory.md), with 764 rows and spell/class reverse indices.
- [Every textual condition and parsed structure](class-condition-gap-inventory.md), preserving exact native parser mapping, source signatures, providers, blockers and reverse indices.
- [Every area prototype and lifecycle gap](class-native-area-contracts-20261007.csv).
- [Every native selector mask and source recognition status](class-native-target-selector-contracts-20261007.csv).
- [Shared family route gaps excluding creature creation/control](non-summon-gap-inventory-20261007.md), now pinned to the final typed graph.
- [Exact persisted/native definition comparison](class-native-catalog-comparison-20261007.json).
- [Combined machine-readable index](class-mechanic-gap-index-20261007.json).

- [Separate complete casting-table and root denominator](class-casting-gap-inventory-20261007.md):851 spells,968 expressions,672 conditional rows,62 function names (5 casting-only),2152 root selectors/geometry contracts. Raw expressions and all flags/levels are preserved; original casting ASTs attached for all968 expressions.
- [Conditional LoS state/passive inventory](class-conditional-los-inventory-20261007.json) and [whole-family obstacle acceptance](conditional-obstacle-acceptance-20261007.md). These describe source/bounded evidence, not live client acceptance.

## General-to-specific priorities

1. Shared state/event application, retention, timer, expiry, decurse and actor fact contracts across 764 state dependencies; distinguish selected executable roots from references.
2. Casting criterion/context contracts: 968 expressions, 672 conditional rows, 62 predicate names including five absent from effect-only denominator; conditional LoS and obstacles depend on effective state/passive selection.
3. Actual activation/trigger producers: IsActivatedByElement (7 classes/92 direct effect definitions), IsActivatedBySpell (4/21), critical/facing/AI actor facts; dependency reachability remains unknown.
4. Generic native ENUTROF_DEPOSIT prototypes202–205 and WALL1605 (5 prototypes), rather than individual spell-ID fixes.
5. Class-specific Symbiot captured-ability and transformation/source contracts, then complete semantic sequences and manual client acceptance.

Current source checkpoint: controller predicates IsOriginalController, CasterAndTargetHaveSameOriginalController and UseGateTriggeringEffect are implemented (reported51 unit tests/64 native oracle cases). The9-case UseGate snapshot has no unsupported predicate;5 actor,2 retention and2 twV context blockers remain. The refreshed condition inventory has98 partial/18 absent and0 raw parse failures. Selector44/46 gaps in prior tables are historical, now all108 masks recognized. Family28 integration is in progress and is not accredited in the145/177 historical registration checkpoint. A65% planning estimate is not a measured functional result.

Three natively missing states 759/7986/8873 remain guarded structural references, not automatic class failures. Historical priority tables remain historical. Zero accredited complete contracts does not mean 0% functionality, and no scenario or registration ratio is promoted to overall completion.

[Owned captured-roster component](native-captured-roster-component-20261007.md) now supplies validated offline persistence records and the exact original codec; owned store hydration and verified BREED_SPECIFIC bootstrap hooks are implemented; migration075 is unapplied, combat wiring and dynamic captured ability compilation remain pending.
