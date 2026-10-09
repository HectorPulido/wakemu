# Native arena selected-surface indices

The ordinary `combat_terrain.local_arena` producer now obtains verified ordered native QI surfaces for the actual map and supplies an explicit XY-to-index mapping to `combat_wire.arena`. It records the catalog's plain native surface provenance with the arena result. This corrects selected altitudes that occupy a nonzero native Vy slot, without changing movement-cell selection, placement, obstacle identities, or blocked cells outside the selected set.

`native_surface_indices` uses only the first native chunk containing XY. The selected altitude must match exactly one ordered Vy entry and its index must fit mask bits 0..5 (0..63). Missing chunks, empty columns, absent or duplicate altitude matches, duplicate selected XY, invalid coordinates and unencodable indices reject. A blocked bLD=-1 surface remains an identifiable surface; native QI.j applies its separate availability rule.

The wire builder requires an explicit mapping to contain exactly all selected XY and strictly integer indices 0..63. Omitted mappings remain index-zero synthetic fixtures; the ordinary local arena producer always provides authoritative indices. No border-bit policy is inferred from geometry.

Pure validation: `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_qi_surface_selection test_combat_qi_surfaces test_combat_wire` — 15 tests pass. Tests cover a nonzero-index topology roundtrip, actual QI.i/j selection, signed bLD, first matching empty chunk, duplicate/missing/capacity rejection, and independent placement/occupancy preservation. These tests do not establish full-map equivalence or GUI behavior; bulk map validation and catalog provenance integration are separate checks. No services, Docker, database or running client operations were performed.

## Published catalog integration

The published loader and ordinary producer were exercised together. An actual radius-12 arena at map1134 origin `(61,-128,50)` and target `(61,-129,50)` contains118 selected cells, including one nonzero native surface index. All118 selected native i/j calls agree with their exact selected XYZ.

The complete map's37,157 movement XYZ entries were checked individually against ordered native surfaces;502 require nonzero indices. There are zero selected-i or selected-j mismatches. XYZ entries are evaluated individually because the full map has stacked floors sharing XY; a single arena correctly requires only one selected altitude per XY. This is Python integration against the separately native-verified surface catalog, rather than a new independent client oracle. Evidence and stable before/after source/catalog hashes are recorded in `native-arena-surface-selection-review-20261007.json`.

`audit_class_initialization.py` now uses the same index selector, stores plain native surface provenance on each Fight, and includes publication, manifest and map1134 output hashes in its tracked evidence. Its initialization suite was not rerun as part of this lightweight producer task.

Expanded tests: `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_terrain_surface_integration test_combat_qi_surface_selection test_combat_qi_surfaces test_combat_wire` —18 tests pass. Integration tests additionally exercise two temporary map catalogs, the immutable cached publication, native decoding failure rejection, source/output hash mismatch rejection and the actual nonzero floor arena.

## Shared active/passive fixture producer

The active spell auditor's `fixture` now supplies exact native selected-surface indices and catalog provenance before ordinary `create_placement`. Passive activation reuses that fixture, so its construction also follows the same producer. Active/class initialization source manifests include the published catalog via `audit_class_initialization.source_hashes`; Ready/passive source manifests now independently include publication, manifest and map1134 payload plus all four audit tool sources. `py_compile` passes for the three changed tool modules. Full spell/passive cycles remain a separate validation step.

The earlier `native-arena-surface-selection-review-20261007.json` remains a historical checkpoint: its captured auditor hash precedes this shared active/passive fixture update. It proves the surface producer and actual map comparison at that captured state, without attesting these later auditor edits.
