# Remaining 13 classes: complete inventory register

Historical inventory-only baseline: this review originally covered thirteen classes at **5/18**. Current user-provisional acceptance is **12/18**; Enutrof, Steamer, Eliotrope, Sadida, Rogue and Xelor remain. The baseline data below is preserved for reproducibility and does not describe subsequent implementation progress. See the [current priority register](../next-class-priority-20261010.md). No combat changes, database writes, deployments or restarts were performed by this inventory review.

## Class reports and machine inventories

| Native ID | Class | Active | Passive | Extra/granted | States | Fixed profiles | Areas | Review | Machine data |
|---:|---|---:|---:|---:|---:|---:|---:|---|---|
| 1 | FECA | 21 | 18 | 2 | 66 | 0 | 9 | [Review](1-review.md) | [JSON](1-inventory.json) |
| 3 | ENUTROF | 21 | 17 | 4 | 46 | 5 | 8 | [Review](3-review.md) | [JSON](3-inventory.json) |
| 4 | SRAM | 21 | 15 | 9 | 29 | 1 | 3 | [Review](4-review.md) | [JSON](4-inventory.json) |
| 5 | XELOR | 21 | 20 | 3 | 46 | 4 | 25 | [Review](5-review.md) | [JSON](5-inventory.json) |
| 6 | ECAFLIP | 21 | 20 | 16 | 79 | 3 | 1 | [Review](6-review.md) | [JSON](6-inventory.json) |
| 10 | SADIDA | 21 | 20 | 3 | 72 | 8 | 9 | [Review](10-review.md) | [JSON](10-inventory.json) |
| 12 | PANDAWA | 21 | 17 | 5 | 43 | 1 | 1 | [Review](12-review.md) | [JSON](12-inventory.json) |
| 13 | ROUBLARD | 21 | 20 | 4 | 74 | 4 | 7 | [Review](13-review.md) | [JSON](13-inventory.json) |
| 14 | ZOBAL | 21 | 19 | 5 | 44 | 0 | 2 | [Review](14-review.md) | [JSON](14-inventory.json) |
| 15 | OUGINAK | 21 | 19 | 4 | 36 | 1 | 3 | [Review](15-review.md) | [JSON](15-inventory.json) |
| 16 | STEAMER | 21 | 20 | 4 | 35 | 2 | 4 | [Review](16-review.md) | [JSON](16-inventory.json) |
| 18 | ELIOTROPE | 21 | 20 | 3 | 37 | 0 | 12 | [Review](18-review.md) | [JSON](18-inventory.json) |
| 19 | HUPPERMAGE | 26 | 18 | 3 | 49 | 0 | 6 | [Review](19-review.md) | [JSON](19-inventory.json) |

The register enumerates **521 primary active/passive spells**, **65 extra/granted spell records**, all spell/innate typed dependencies, secondary states, linked fixed summon profiles and their books, areas, native criteria, subscription/event metadata, parameters, typed dependency edges and applicable mechanic requirements. Shared dependencies may occur in several classes; column sums are not a unique global mechanic count. Fixed profile counts exclude separate copy/temporary/derived profiles, explicitly discussed in each review (for example Zobal copy profile 2382).

## Current authority and reproducibility

[Published catalog reconciliation](published-catalog-reconciliation.json) verifies all thirteen rosters, kinds, unlocks, names and innate seeds; all 65 extra trees and their grant effects; and 29 unique class-referenced fixed summon profiles with book definitions. It pins complete PostgreSQL revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`. The absent filesystem protocol directory is intentional. [Source audit](../remaining-classes-source-audit-20261010.md) records document hashes, source provenance, read-only queries and limitations.

[Current runtime routes](../class-effect-route-inventory-20261010.md) were regenerated from current shared code and PostgreSQL: 161 registered and 23 construction-gated families, with no unregistered family in its declared scope. This proves registration only.

Rebuild the structural per-class indexes after the route matrix is refreshed:

```sh
python3 server/tools/build_remaining_class_inventory.py
```

The generator checks source stability, records SHA-256 and writes [the machine index](index.json). Native raw definitions and level samples remain in the linked hash-pinned source graph; per-class JSON preserves identity, typed edges and key contract metadata without replicating that entire graph.

## Behavior and risk inventory

Each class review includes resources, state producers and secondary reactions, summon control/book/retirement, areas and ownership, temporary actions/appearance, targeting and LOS, event order, durations, removal, rejection atomicity, reconnect, death and fight completion. It distinguishes native definitions, present runtime support, bounded historical execution evidence and unverified gameplay/client behavior. Shared fixes from Cra, Iop, Sacrier, Eniripsa and Osamodas are linked with applicability limits.

Primary high-risk systems are Feca shields/glyphs; Enutrof deposits/transformation/Drheller; Sram traps/invisibility/double; Xelor dial/time resources/position; Ecaflip random branches/tarot/summons; Sadida dolls/voodoll/control; Pandawa carry/barrel/drunkenness; Rogue bombs/walls/chains; Zobal masks/copy; Ouginak prey/rage/transformation; Steamer turrets/rails/alternate mode; Eliotrope portals/pathing; and Huppermage elemental runes/quadramental resource/temporary actions. These are review priorities, not newly reproduced defects.

## Explicit unknowns and completion boundary

This inventory is exhaustive for the declared catalog rosters and preserved typed-reference contracts, and records unclassified producers rather than silently omitting them. Native graph reference semantics, context-derived/copy/morph books and dynamic reachability are not all classified; the source audit and per-class reviews list those residual investigation requirements. Presence in a static dependency closure is not proof that a branch is reachable or that a mechanic works. No numerical implementation percentage is inferred and no new class is marked playable.

The next implementation phase should use these exact IDs and risks to verify complete systems, with the five accepted classes as regression controls. It requires a separate authorization/request; this task remains inventory only.

[Inventory consistency validation](validation.md) checks every class roster, typed membership, outgoing edge, profile book, requirement mapping and artifact hash. The preserved graph has no external edge targets for these class memberships; unclassified reference producers are explicitly listed as coverage follow-up, not hidden or counted as functionality.

Current six-class estimates and refreshed evidence: [remaining six refresh](../remaining-six-refresh-20261010/README.md). Historical denominators below retain their original scope.
