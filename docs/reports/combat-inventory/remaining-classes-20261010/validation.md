# Remaining class inventory validation

Validated the 13 generated class inventories and `index.json` against their pinned source exports. This is an exhaustiveness and consistency audit of the generated data, not a gameplay or runtime-behavior verification.

## Result

The generated inventories contain **521 owned primary spells** (278 active, 243 passive) and **65 extra/granted spell records** across 13 classes. All per-class owned spell rows and extra spell rows match `inventory.json` exactly. Class IDs, names, roster counts, file digests, source digests, and index digests agree. The published catalog reconciliation reports the same roster and innates for all 13 classes; the 65 extra spells have no missing published grant-effect definitions.

For each class, the generated typed-node membership equals the union of its spell and innate component membership, including exact per-node scopes. Every outgoing edge from those member nodes is represented with matching multiplicity. Every referenced native ability profile and its ability-reference spell nodes are present. There are no edge targets outside the generated membership. Requirement-unit IDs and `class_nodes` mappings match the class-specific records in the pinned requirements export.

| Breed | Class | Active | Passive | Extras | Typed nodes | Graph edges | Profiles | Requirement units |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Feca | 21 | 18 | 2 | 1,853 | 4,684 | 0 | 191 |
| 3 | Enutrof | 21 | 17 | 4 | 1,230 | 2,891 | 5 | 226 |
| 4 | Sram | 21 | 15 | 9 | 1,256 | 2,357 | 1 | 216 |
| 5 | Xelor | 21 | 20 | 3 | 1,647 | 3,387 | 4 | 216 |
| 6 | Ecaflip | 21 | 20 | 16 | 2,018 | 5,185 | 3 | 236 |
| 10 | Sadida | 21 | 20 | 3 | 1,907 | 4,247 | 8 | 237 |
| 12 | Pandawa | 21 | 17 | 5 | 1,095 | 2,324 | 1 | 210 |
| 13 | Rogue | 21 | 20 | 4 | 3,397 | 8,866 | 4 | 228 |
| 14 | Mask | 21 | 19 | 5 | 1,115 | 2,331 | 0 | 206 |
| 15 | Ouginak | 21 | 19 | 4 | 1,336 | 2,851 | 1 | 228 |
| 16 | Foggernaut | 21 | 20 | 4 | 1,273 | 2,971 | 2 | 220 |
| 18 | Eliotrope | 21 | 20 | 3 | 1,302 | 2,888 | 0 | 203 |
| 19 | Huppermage | 26 | 18 | 3 | 1,758 | 3,853 | 0 | 206 |
| **Total** |  | **278** | **243** | **65** | **21,187** | **48,835** | **29** | **2,823** |

The generator declares five accepted review classes and 13 inventory classes; the generated data covers all 13 classes in the inventory source. `index.json` pins the generator inputs with SHA-256 digests and reports `sources_stable: true`. Source dates matter: the typed graph/components and requirements exports are dated 2026-10-07, while the route inventory is dated 2026-10-10. These outputs are complete relative to those pinned exports; they do not demonstrate closure over dynamic/runtime sources that the graph exporter does not classify.

## Coverage boundary and follow-up

The requirements export contains a `native_reference_slot_classification_unverified` family set: 178 families and 19,398 distinct effect references are marked `not_classified_by_this_exporter`, with `is_reference_producer: null`. Some intersect each class's static spell/innate dependency closure. This is an **unclassified reference-producer/source-attribution coverage gap**. It does not mean those effect definitions or routes are missing, and it does not prove a feature is broken. Track this as a coverage gap until reference-producing semantics and dynamic reachability are classified; do not report it as completed functional coverage.

Two older requirements records flag `native_definition:state:8873` (Enutrof) and `native_definition:state:7986` (Rogue) with `native_missing: true` and dynamic reachability unknown in the 2026-10-07 graph export. Those flags describe that historical export's source-definition evidence. The corresponding graph nodes are placeholders, so a generated `source_definition_present` field must not be read as proof that a current native definition exists. Resolve against current catalog/state evidence before making any current missing-definition or functional claim. The PostgreSQL published-catalog reconciliation is authoritative for its stated roster/innate/grant checks; the static snapshot should retain its date boundary.

## Evidence and machine data

- Generator: [`build_remaining_class_inventory.py`](../../../../server/tools/build_remaining_class_inventory.py)
- Generated index and source hashes: [`index.json`](index.json)
- Machine-readable inventories: [`1-inventory.json`](1-inventory.json), [`3-inventory.json`](3-inventory.json), [`4-inventory.json`](4-inventory.json), [`5-inventory.json`](5-inventory.json), [`6-inventory.json`](6-inventory.json), [`10-inventory.json`](10-inventory.json), [`12-inventory.json`](12-inventory.json), [`13-inventory.json`](13-inventory.json), [`14-inventory.json`](14-inventory.json), [`15-inventory.json`](15-inventory.json), [`16-inventory.json`](16-inventory.json), [`18-inventory.json`](18-inventory.json), [`19-inventory.json`](19-inventory.json)
- Current published catalog reconciliation: [`published-catalog-reconciliation.json`](published-catalog-reconciliation.json)
- Current route inventory: [`class-effect-route-inventory-20261010.json`](../class-effect-route-inventory-20261010.json)
- Pinned static source exports: `docs/reports/combat-inventory/class-native-mechanic-graph-20261007.json`, `class-native-mechanic-components-20261007.json`, `class-mechanic-requirements-20261007.json`, and `inventory.json`.
