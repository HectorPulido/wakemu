# Class-only bulk closure review — 2026-10-07

The direct class catalog already contains the executable effect definitions reached by the classified reference mechanisms. Replacing it with all 4,143 staged spell trees would not, by itself, resolve the shared combat blockers. Keep the next work centered on native criteria, effective casting range/resources, delivery ownership, passive event ordering and summoned-actor lifecycle.

This review is read-only. It follows 722 class spells, the 91 known class-linked extras, and native innates for 18 classes through group children and families 304 (state), 315 (area), 649 (granted spell), and separately 307 (summon). It uses compact maps read from staging TSVs and streaming JSON entries, rather than constructing the runtime catalog. No production code, protocol catalog, service, database, AI or client was changed.

## Structural result

| Scope | Spell trees | States referenced | Areas | Effects | Missing local spell trees | Missing local effects |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Class spells, extras and innates | 813 | 753 | 79 | 20,831 | 0 | 0 |
| Including only abilities of class-referenced summoned entities | 851 | 760 | 81 | 21,177 | 38 | 297 |

The first row is a structural over-approximation: all exported branches are followed without executing conditions. Its effect variants comprise 15,360 records with variant 0 and 5,471 with variant 1. It encounters 140 grant-reference edges, 481 area-reference edges and 2,990 state-reference edges; fixed-point traversal discovers no additional player spell trees beyond the 813 seeds. No scaled reference slot was observed in these classified reachable families.

“Local” here means the union of class, granted, state and area tree files. The ordinary compiled catalog merges those sources when `WAKFU_NATIVE_GRANTED_CAST=1`; granted definitions are excluded when that flag is disabled. This review does not inspect the running server's environment or its process-lifetime catalog cache.

The second row is a dependency boundary, not a proposal to import the general monster catalog. Family 307 references 39 existing entity profiles. Their native ability lists introduce 38 further spell trees and 297 effects absent from the local union but present in staging. Those IDs remain a separate staged dependency list in the accompanying JSON. General monster integration remains deferred. Their presence does not establish summon ownership, initialization, AI or lifecycle support.

## Three missing state references are guarded obsolete branches

The all-state staging export and the local state catalog both lack references 759, 7986 and 8873. The references come from the first evaluated parameter of family 304, consistent with `interpret_state_parameters`; they are not inferred from spell names. They are positive IDs below the signed-short boundary. The relevant effects have variant 0, definition bounds 0–32767 and 200 native parameter samples from the exporter.

| State | Structural owner | Reference evidence | Guard qualification |
| --- | --- | --- | --- |
| 759 | Class 11 native innate state 3702 | Applicators 316596, 316615, 316608 | A shortest ancestry includes group 415999 with `not IsSpellInDeck(5193) and False`. |
| 7986 | Class 13 | Applicator 371126 | The applicator criterion is `False`; its parent also ends in `and False`. |
| 8873 | Class 3 native innate state 3652 | Applicators 394229, 394230 | Each criterion is `IsInFight() and False`. |

A separate conservative boolean analysis parsed criteria and folded only literal booleans, `and`, `or` and `not`; calls and comparisons remained unknown. After dropping branches whose result is unconditionally false, all three unresolved state references disappear. The resulting classified closure still contains 813 spell trees, with 734 referenced states, 78 areas and 19,160 effects. This is evidence of obsolete guarded references, not a reason to fabricate missing states or silently remove native definitions.

Logical false guards also do not prove the current evaluator avoids errors while evaluating an unsupported left operand before reaching `False`. Preserve the original guards and ancestry in any import, and distinguish a condition-evaluation defect from an absent actionable state definition. Full dynamic reachability remains **unknown**.

## A strict class-only import mechanism

Use one generic, provenance-checked importer rather than extracting or patching individual spells:

1. Start from native class identities, class innates and the known class-linked grant seeds. Follow every native exported root/child and classified state/area/grant reference to a fixed point. Preserve ownership links and original normal/critical branches. Keep summon ability dependencies as a separate section while monster integration is deferred.
2. Select only the resulting class closure from the staged dataset. Reject missing actionable references and identity conflicts. Record constant-false obsolete references explicitly with their guard ancestry; do not manufacture placeholder definitions. Reject or mark unknown any unclassified reference producer or unsampled dynamic reference domain.
3. Join the complete authoritative casting contract for those IDs: conditional range/resource tables, `range_modifiable`, LOS/alignment/free-cell and self-target policies, spell limits, categories/AP modifiers, elements, critical availability and native maximum levels. The staged range-flag extraction already supplies a source for the flag, but a flag alone is not the effective range calculation.
4. Preserve native effect parameters and sampled evaluations, criteria, targets, area shapes, probability, timing, retained metadata, HMI actions, state application/removal policy and event subscriptions. Produce a per-section source manifest and a complete old/new semantic diff before replacing any catalog. Boundaries and signed-short state levels require explicit native evaluation rather than extrapolation from the 1–200 state samples.
5. Treat importer completeness and engine capability as separate checks. A successful import must not mark criteria, family handlers, event producers, delivery ownership or summon lifecycle as implemented. Validate those shared mechanisms against their dependents after implementation.

The importer proposal above is not implemented or integrated by this review. Given the zero direct-definition gaps found here, additional bulk import is a secondary data-integrity task, while shared engine fixes are the immediate path to working class combat.

## Provenance and limits

[class-only-bulk-closure-20261007.json](class-only-bulk-closure-20261007.json) contains compact counts, classified closure details, the 38 deferred summon-ability IDs, the three state ancestry witnesses and source SHA-256 values. Recorded hashes match the files at the end of analysis. The four local tree catalogs also match the original catalog hashes captured by the bulk staging inspection; staging verification reported unchanged export inputs. A pre/post manifest around the entire review process was not collected, so source stability for every instant of that process is not asserted.

Class gameplay coverage is **unknown**. This analysis does not certify other native transformation/replacement/reference families, references encoded in criteria, negative or boundary parameter domains, equipment/aptitude interactions, legal conditions, combat transactions or graphical delivery. Staged completeness across all native spells is not equivalent to complete class behavior.
