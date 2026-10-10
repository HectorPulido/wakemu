# Remaining 13 class inventory source audit — 2026-10-10

## Scope and conclusion

This audit covers the 13 classes left after the accepted Cra (9), Iop (8), Sacrier (11), Eniripsa (7), and Osamodas (2): Feca (1), Enutrof (3), Sram (4), Xelor (5), Ecaflip (6), Sadida (10), Pandawa (12), Rogue (13), Zobal (14), Ouginak (15), Steamer (16), Eliotrope (18), and Huppermage (19). IDs are original native breed IDs, not row positions.

The freshest broad, source-attested typed graph available is `class-native-mechanic-graph-20261007.json` (indexed from the original native-client export on 2026-10-07; report copy last refreshed 2026-10-09). It covers all 18 classes, including passives, class innates, class-referenced fixed summon profiles, nested selected effect roots, states, and areas. Its counts are 851 spell nodes, 764 state nodes, 39 summon-profile nodes, 21,207 effect nodes, and 90 area nodes. It is the best starting point for these 13 classes; no more recent all-class typed graph was found. Later, narrower native closures supplement it for Osamodas capture (2026-10-08), Sacrier transformation (2026-10-08), and cross-class triggered family 426 (2026-10-08).

The graph is a structural/native-definition inventory. It does not establish criterion truth, runtime reachability, complete client behavior, or that every stored passive/state/summon branch works. Keep those distinctions in the next class inventories.

## Per-class denominator

`Class spells` and active/passive counts below come from `inventory.json`; extras are separately linked granted spells. The final four columns are unique native component references in that class's spell plus innate dependency components, not runtime-executed counts. Shared references can occur in multiple class rows.

| ID | Class | Class spells (active / passive) | Extra granted spells | Spell nodes | Effects | States | Profiles | Areas |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Feca | 39 (21 / 18) | 2 | 41 | 1,592 | 66 | 0 | 9 |
| 3 | Enutrof | 38 (21 / 17) | 4 | 49 | 980 | 46 | 5 | 8 |
| 4 | Sram | 36 (21 / 15) | 9 | 49 | 1,041 | 29 | 1 | 3 |
| 5 | Xelor | 41 (21 / 20) | 3 | 44 | 1,363 | 46 | 4 | 25 |
| 6 | Ecaflip | 41 (21 / 20) | 16 | 59 | 1,681 | 79 | 3 | 1 |
| 10 | Sadida | 41 (21 / 20) | 3 | 53 | 1,572 | 72 | 8 | 9 |
| 12 | Pandawa | 38 (21 / 17) | 5 | 43 | 902 | 43 | 1 | 1 |
| 13 | Rogue | 41 (21 / 20) | 4 | 49 | 3,042 | 74 | 4 | 7 |
| 14 | Zobal | 40 (21 / 19) | 5 | 45 | 862 | 44 | 0 | 2 |
| 15 | Ouginak | 40 (21 / 19) | 4 | 48 | 1,130 | 36 | 1 | 3 |
| 16 | Steamer | 41 (21 / 20) | 4 | 45 | 1,063 | 35 | 2 | 4 |
| 18 | Eliotrope | 41 (21 / 20) | 3 | 44 | 1,039 | 37 | 0 | 12 |
| 19 | Huppermage | 44 (26 / 18) | 3 | 47 | 1,508 | 49 | 0 | 6 |

These are source denominators, not counts of finished implementations. The game-client review catalog [`inventory.json`](inventory.json) covers 722 class spell records / 91 extras overall and explicitly scopes itself to the installed client's class catalog, not the entire NPC spell catalog. It contains spell-level roots, levels, criteria and manual review fields, while the larger native graph contributes raw native metadata and typed dependency edges.

## Authoritative artifacts and provenance

| Purpose | Artifact and exact scope |
|---|---|
| Main all-class typed source graph | [`class-native-mechanic-graph-20261007.json`](class-native-mechanic-graph-20261007.json), 111,878,559 bytes; 851 spells, 764 states, 39 profiles, 21,207 effects, 90 areas. Scope: 813 class definitions (722 class spells + 91 extras), 22 native innate states, and only class-referenced summon profiles. |
| Original exported rows | `.runtime/combat-review-20261007/mechanic-graph/native-graph.jsonl.gz`, SHA-256 `3aa8ccc9e4029cdd184f50414f746a0c35fc5a0c87a4223c8ba081c410b3fc12`. This is the native-client row source indexed into the public graph. |
| Per-class ownership and component matrix | [`class-native-mechanic-components-20261007.json`](class-native-mechanic-components-20261007.json) and [`class-native-mechanic-components-20261007.csv`](class-native-mechanic-components-20261007.csv): all 18 breed IDs, class/extra spell roots, separate spell vs innate dependency components, class-linked profiles, states, effects, areas, and unknown definitions. |
| Native spell cast roots/conditions | [`class-casting-gap-inventory-20261007.json`](class-casting-gap-inventory-20261007.json): all 851 scoped spell definitions present, 968 criterion expressions, 672 conditional rows, 2,152 native root contracts, zero missing spells. It includes fixed class-summon dependency spells but excludes dynamic captured species. |
| State status overlay | [`class-state-gap-inventory.json`](class-state-gap-inventory.json): the same 764 native class-dependency states; 79 partial, 682 pending verification, 3 absent (759, 7986, 8873), zero complete semantic or client states. |
| Passive evidence overlay | [`class-passive-mechanic-gap-inventory-20261008.full.json`](class-passive-mechanic-gap-inventory-20261008.full.json): all 339 class passives, 18 classes, 339 ready observations, 323 complete observed end/ack/start cycles and 16 unavailable cycles. This is evidence about bounded scenarios, not full passive semantics. |
| Shared effect route overlay | [`class-effect-route-inventory-20261008.json`](class-effect-route-inventory-20261008.json): exact 18-class graph plus Osamodas capturable/nested profiles; 161 registered and 23 gated families. Registration/factory presence does not prove parameters, guards, delivery, or lifecycle. |
| Cross-class triggered closure | [`class-triggered426-native-typed-closure-20261008.json`](class-triggered426-native-typed-closure-20261008.json) and adjacent `.jsonl.gz`: 5 source spell definitions, 314 effects, 12 states for original family-426 target spells referenced by 18-class source effects. Parent runtime reachability remains pending. |
| Osa capture-only closure | [`class-captured-native-typed-closure-20261008.json`](class-captured-native-typed-closure-20261008.json) and adjacent `.jsonl.gz`: Osa ID 2 only; 41 profiles, 195 spells, 178 states, 2,156 effects, 21 areas. Not applicable as an owned class feature for the 13 remaining classes, but relevant to keeping dynamic captures separate from the fixed-summon denominator. |
| Sacrier morph-only closure | [`class-morph933-native-typed-closure-20261008.json`](class-morph933-native-typed-closure-20261008.json) and adjacent `.jsonl.gz`: Sacrier ID 11 only; 1 profile, 3 spells, 141 effects, 15 states, including 60 added and 60 zero-level effects. Its own temporary spellbook/lifecycle audit remains pending; do not generalize it to other transformations. |

The main graph metadata reports `sources_stable: true` for the tracked inputs and records the original exporter as `sniffer/java/ExportClassMechanicGraph.java`. Its companion source set includes `sniffer/java/ExportClassSummonEffectTrees.java`, `sniffer/java/ExportEffectRuntimeMetadata.java`, the then-exported summon ability catalog, native protocol definitions, and the graph seeds. Those paths describe the historical native-client export inputs; the current runtime catalog authority is the published PostgreSQL release documented below. The graph's current SHA-256 is `023b85574c21c024cc38c4f92191ad28dabf8ce00df679600a70749316c6888d` (the value recorded as `graph_sha256` by the graph summary).

## Coverage limits that matter for the remaining classes

- **Class spells/passives:** There is an exact native spell denominator and passives have a global 339-case observation audit, but its 688 selected actions include 17 unresolved eligibility cases, 77 bounded-search-exhausted cases, and 35 rejected effect transactions. It reports 3,861 omitted action occurrences (3,711 spell/level/class/origin units). No passive is marked game-verified; do not call the 339 passive definitions functionally complete.
- **States / secondary state behavior:** The 764-state structural set includes class spell and innate dependencies. The state overlay has 0 fully verified semantic states and 0 fully verified client states. Three native definitions are absent; 682 await verification and 79 are partial. Branch inclusion is conservative and does not mean a state is reachable or legally applicable.
- **Summons:** The broad graph follows only 39 class-referenced profiles and their exposed ability books; no general monster/AI execution is included. Profiles and summon spell nodes in class tables are definitions/dependencies, not proof of creation, control, turns, delivery, removal, or client display. Osamodas' 33 capture-eligible profiles plus 8 nested profiles belong to its separate closure, not the 13-class denominator.
- **Morphs and transformed/temporary books:** The specific family-933 projection is Sacrier-scoped. The all-class graph explicitly lists full transformation classification as unproved. Audit temporary book changes, borrowed spells, level-zero roots and their grant/lifecycle paths per remaining class where present; do not treat 933's Sacrier results as a universal morph extraction.
- **Typed-reference completeness:** The graph proves selected reference contracts for state family 304, configured native area runners (`eYQ` families), grant 649 slot 2, and summon 307 slot 0. Other producers, context-derived references and criterion-embedded references remain unknown. The raw graph preserves unknown/unexpanded native nodes; it does not silently resolve them.
- **Execution and client:** Native source samples preserve roots, ordering, criteria, fields, masks and timings; they do not execute runner code or prove a live branch. Registered handlers, prepared transactions, movement, or end/start cycles alone do not establish complete spell/passive semantics or client application.

## Reproducible extraction recommendation

1. Treat the native client/runtime version and its exported source set as a pinned input. Recreate the exact seed set using `python3 server/tools/build_class_mechanic_graph.py --prepare`; record and compare `.runtime/combat-review-20261007/mechanic-graph/sources-before.json` against the end-of-export hashes.
2. Run `sniffer/java/ExportClassMechanicGraph.java` against that same installed client after its native protocol/class loaders are initialized, writing the line-oriented native rows to `.runtime/combat-review-20261007/mechanic-graph/native-graph.jsonl.gz`. Preserve level 0..245 and signed-boundary samples, ordered roots, raw criteria, native fields and explicit missing/unexpanded markers. Do not substitute the server's local gameplay implementation for the original-client authority.
3. Index the rows with `python3 server/tools/build_class_mechanic_graph.py`; then regenerate class ownership/components with `python3 server/tools/build_class_mechanic_components.py` and spell access/casting overlays with their dedicated inventory builders. Compare input hashes before/after and reject a run if the source changed or an identity check fails.
4. Keep overlays separate: merge the applicable class-scoped summon/morph/trigger closures only after their source-specific exporter and ownership rules have been confirmed. For every new class, retain separate lists for primary class books, passives, innate states, fixed summon profiles, grant/trigger books, temporary/morph books, and state/effect/area dependencies. Unknown edge producers should remain explicit unknowns until their native parameter contract is demonstrated.
5. Convert structural inventory into a behavior queue only after joining each row to its exact native root/criterion, runtime provider, state lifecycle, summon/book lifecycle and client-delivery proof. Use one system-level test plan per mechanic family, then class-specific probes for distinct native contracts; track unresolved branches instead of inflating a coverage percentage.

Commands above describe the reproducible tools/flow. This audit did not run exporters, alter gameplay code, operate services, or write to a database.

## Published catalog authority and reconciliation

`server/protocol/` was deliberately removed after catalog migration; its absence is not a missing catalog, source gap, or runtime defect. [`server/wakfu_server/storage/native_catalog.py`](../../server/wakfu_server/storage/native_catalog.py) pins one complete `native_catalog_active` revision, reads immutable `native_catalog_documents`, and validates each raw document against its stored SHA-256. Redis is a bounded cache. For this source audit, I bypassed the application reader/cache and used direct PostgreSQL SELECTs inside `BEGIN READ ONLY`, so the check did not write to PostgreSQL or Redis.

The active published release is `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`: `complete=true`, 7,483 documents, 2,269,452,622 source bytes; activated at `2026-10-09T18:16:18.491831Z`, completed at `2026-10-09T18:56:50.705041Z`. All document hashes below were recomputed over the returned `raw` bytes and matched the stored hash.

| Published document | SHA-256 | Bytes | Records | Relevant coverage |
|---|---|---:|---:|---|
| `spells.json` | `44fcaea5a01906d1247079fe14e861ddc2b375486aa72eaaeabc976774b98fea` | 88,073 | 730 | Spell definitions, breed ownership, kind and unlock level |
| `spell-names.json` | `7a76a231b133b20499edd9bc98917596f9e5a163f713d0717d87de699831325f` | 58,731 | 742 | 722 localized spell names and 18 class labels |
| `spell-effect-trees.json` | `a188b3681c79ad455d296b303491370419cbe23da130501a8b86b51bd9a518ba` | 57,514,368 | 12,293 | Primary spell effect trees |
| `granted-spell-effect-trees.json` | `2d07839bdf094a23cd6cba02da6853766bc21f82244b59a1d2fcdc3bfb903477` | 14,203,360 | 3,096 | Granted spell trees and nested effects |
| `breed-innate-definitions.json` | `99d83aa956797dfdb8746e485dbe267574ef606bf23c71416244e7393558c25d` | 5,640 | 18 | Class resources, innate states and native class book arrays |
| `native-class-casting-roots.json` | `a4db4c2d79c44da164effa8525671ccabdc15b2ab6d60840d30744a33afa8ca7` | 283,178 | 2,160 | Native class casting roots and conditions |
| `native-class-summon-abilities.json` | `3f90d274c512ebc2611e84dceb37acb0f21f6c4b9329b7bd774ce2bdec3dc383` | 7,728 | 39 | Fixed profile ability books |
| `native-class-summon-initial-states.json` | `8946715f461a5eec278a580a9208ad460d3d9800df260a1408b547ea8d3c5466` | 2,829 | 39 | Summon profile properties and initial states |
| `native-class-morph-profiles.json` | `3861759f2e71b360b4812cc3424a0fe3255be2d7dc72a496778558bcf86ee8f8` | 933 | 6 | Sacrier-only profile 5900 in this revision |
| `native-class-copy-profiles.json` | `af006b532503631153736f80a06af02b81204ce5d544b00aea9d38a93dd460d7` | 720 | 6 | Copy profile 2382, with effect edge 413075 (Zobal dependency) |
| `native-class-spell-grant-closure.json` | `14f511d4e86436584f7a4376f0421b74c0ac94dc16773bad83cbd74d3741b6e2` | 77,239 | 6,428 | Grant effects, typed effect references and granted-spell references |
| `combat-state-definitions.json` | `845f211b808b9ce20a14b25f3e3068480094243c507e4aaa8f9da5fad5bca7b9` | 269,576,853 | 50,081 | 6,129 state and 43,952 effect records |
| `native-effect-areas.json` | `e4b888bf1ddcb5a19f9c74cbb842daee6e81a3892786c32622b84b61f7329dff` | 1,386,284 | 1,440 | 1,436 native area definitions |
| `native-spell-casting.json` | `0e6ef6f9f3bd4f3c4192a77673fd0598034e51d1149364d66f5f24f5ff6095c9` | 34,394,282 | 4,148 | 4,143 native spell-casting records |

The machine-readable proof [`published-catalog-reconciliation.json`](remaining-classes-20261010/published-catalog-reconciliation.json) covers all 13 remaining classes and pins the two local input hashes (`inventory.json` and the class component matrix). A direct per-class compare against published `spells.json` and `spell-names.json` found exact agreement on ID, kind, unlock level, and localized name. The active spell roster counts are 40 (Zobal), 40 (Ouginak), 41 (Steamer), 41 (Eliotrope), and 44 (Huppermage); all deltas are empty. Their published innate definitions also match report seeds: Zobal 3769/4464, Ouginak 4464/7521, Steamer 7675/4464, Eliotrope 3398/4464, Huppermage 4069/4464/7562. All 13 roster deltas are empty; all 65 extra/granted spells have published granted-tree definitions; all 29 class-referenced fixed summon-profile IDs have published profile rows, and every listed profile-book spell ID has a published casting or tree definition. Extra-grant effects also resolve across the published primary, granted, and state effect maps. The 13 native innate arrays match. These checks do not assert runtime mechanics or client behavior.

The per-class dependency matrices, class-state status overlay, casting snapshots, and native source graph are still dated structural evidence. Published presence and SHA integrity establish available source data, not semantic completeness. In particular, the broad graph follows 39 fixed class-referenced profiles; class-specific ownership of a profile needs the graph/component edge, while constructor-only copy profile 2382 is outside the class summon-profile count. No current proof is inferred from the old Oct 8 effect-route overlay; a later regenerated route report must be assessed on its own provenance and scope.

The JSON records per-class roster, innates, extras, profile books, missing-reference arrays, active document hashes, and verification flags. A reproducible read-only check is: connect with the project venv to the local database endpoint; execute `BEGIN READ ONLY`; select the active complete revision by joining `native_catalog_active` to `native_catalog_releases`; select requested rows from `native_catalog_documents` by revision and path; recompute SHA-256 over each `raw` byte string; parse JSON and compare class-keyed IDs/fields. For roster comparison, join `inventory.json` rows by `breed` and `id` to `spells.json` and `spell-names.json`; for innates, select matching `breed` rows from `breed-innate-definitions.json`. Always roll back/close the read-only transaction. Avoid loading catalog documents through `native_catalog.read_bytes()` for this audit because the cache can write to Redis on a miss.
