# Class summon dependency import — 2026-10-07

The enabled native granted-spell catalog now includes the previously missing abilities of class-referenced summons. This is a scoped native data import, not certification of summon casting, client delivery or complete class mechanics. No service, Docker container, database, AI or general monster catalog was changed.

## Imported scope

The 39 class-referenced native profiles contain 86 ordered ability records and 43 distinct ability references. Generic structural traversal from those abilities, including their native level-zero roots, reaches 43 spell trees, 40 states, 15 areas and 623 effects. State and area definitions already exist locally. All 319 effect identities from the separate native level-zero export are inside this closure.

`server/protocol/granted-spell-effect-trees.json` gained exactly 38 ability trees and 297 effect definitions, changing its counts from 167 to 205 trees and from 2,589 to 2,886 effects. The enabled existing runtime merge consumes this catalog; no new runtime loader or per-creature exception was added. All original 167 trees and 2,589 effects remain exactly equal to their pre-import records.

`native-class-summon-abilities.json`, created by the summon-casting implementation, remains byte-for-byte identical to the private native profile export. The import does not replace or reinterpret its ability ordering, overrides, casting UIDs or maximum levels.

## Native export and verification

The original full staging export identifies the missing dependency set, but is not sufficient for publication: current local effects contain later timing metadata, and the staged spell flag exporter previously confused free-cell `cwU` with `cwN`. Therefore the import uses a fresh scoped native export rather than copying stale staged missing records directly.

`ExportClassSummonEffectTrees.java` exports all 43 native abilities through each definition's actual maximum level and samples effect parameters/probabilities at levels 1–245. It reads free-cell authority from `cwU`. `ExportEffectRuntimeMetadata.java` separately exports actual definition class, timing checks/definitions, flags, localization and execution mode for all 623 reachable effects. The separate native zero export supplies the level-zero roots and samples; the summon-casting implementation subsequently merged those 43 references into the zero snapshot. Its separate verification also extends the native critical-sample domain. A streaming check confirms all 43 normal native casting tables, including conditional costs/ranges, cover each definition's exact maximum level (6 or 245), with zero missing or shortened tables.

Published verification establishes:

- All 38 new trees exactly equal the fresh native structural trees.
- All 297 new effects exactly equal the fresh native effect records joined with fresh runtime metadata, including all 245 parameter/probability samples.
- No existing local identity conflicts occur across class, granted, state and area sources.
- No referenced state, area, group child or classified grant reference is missing in this scoped closure.
- The complete profile metadata remains equal to its native export.
- All tracked source hashes remained stable while the importer read and published its result. Installed client libraries/data hashes are checked against the native profile-export provenance.

The output catalog SHA-256 is `1c08bcd442c9e5bdf43f093e4cdd6206ad674121614898f9061fbda7cc129ba4`. The original catalog backup and explicit equality verification are private under `.runtime/combat-review-20261007/class-summon-import/`.

The importer logs, but preserves, 91 existing-record differences against the fresh native/staged union. Most are differing timing-check sample domains or older 200-element parameter arrays versus the fresh 245-element arrays. One existing HMI action has a different native allocated action ID despite equal particle/action properties; one shared area-effect record lacks a native area-point field present in staging. These existing definitions were deliberately not overwritten by a dependency import. Identity fields are checked strictly; existing core identity conflicts abort publication.

The compact structural graph sorts child references, so closure verification compares membership. Published definitions retain the original native child order. A first strict comparison correctly aborted before writing when it compared the compact sorted list to native order; the corrected membership check does not sort or rewrite native runtime definitions.

## Reproduction and remaining limits

Run the source-only importer from the repository root:

```sh
python3 server/tools/import_class_summon_dependencies.py
```

Publication uses `--publish`, validates stable source/target hashes, keeps a backup, and replaces the target atomically. The native private exports must already exist; the tool does not launch a client or service. The initial successful publication and explicit preserved-record/exact-native equality checks completed without loading the heavy combat runtime catalog.

Structural traversal classifies children and families 304, 315 and 649. Criteria, implicit references, condition semantics, event subscriptions/producers, retained ownership, native zero runtime integration, controlled request authorization and graphical delivery require their own implementation and tests. Nested family-307 dependencies or scaled reference producers abort rather than silently importing general monster content. A complete data closure is not a complete class-mechanics map or executable proof.

The [machine-readable import report](class-summon-dependency-import-20261007.json) records the exact IDs, existing differences and source provenance. Runtime casting and lifecycle verification are tracked separately in [controlled class summon casting review](controlled-class-summon-casting-review-20261007.md).

## Narrow runtime dependency manifest

`server/protocol/native-class-summon-effect-closure.json` subsequently publishes the 297 imported effect IDs, the complete 623-effect structural closure, and the 43 native ability references with hashed source/import provenance. The summon consumer can compile these imported dependencies independently of the unrelated temporary-grant feature flag. This metadata provides definitions only; it does not authorize casting granted abilities or general monster spells. The original native ability-profile metadata remains unchanged.
