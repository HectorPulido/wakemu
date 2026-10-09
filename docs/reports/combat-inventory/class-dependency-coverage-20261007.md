# Class dependency coverage inventory — 2026-10-07

The global denominator is **813 spell definitions: 722 class spells and 91 class-linked extras, across 18 classes**. Scenario counts are observations against that denominator; they are not the denominator itself. Native innates are also dependencies of every spell owned by the relevant class. Class-referenced summons expose 43 distinct ability references through 39 profiles and 86 ordered records. Their scoped publication adds 38 previously missing trees and 297 effects; the complete summon ability closure contains 623 effects. General monster spells remain outside this review.

The new offline inventory follows the existing compact native closure graph for each spell, including its class innates and the published ability books of its class-referenced summons. It records transitive effect IDs, effect families, state IDs, area IDs, granted spell IDs, summoned entity references, criterion function names and unresolved structural references. The family and condition reverse indices identify all dependent spells, allowing fixes and contract verification to be scheduled by shared mechanism rather than spell ID.

| Inventory dimension | Result | Meaning |
| --- | ---: | --- |
| Spell definitions | 813 | 722 class + 91 extras |
| Classes | 18 | Includes breeds 18 and 19; no breed 17 |
| Reachable effect families | 180 | Includes all sampled branches and innate dependencies |
| Criterion function names | 122 | Function occurrence inventory, not evaluation accreditation |
| Fully verified class behavior | Unknown | No exhaustive semantic definition has been accredited |
| Fully verified graphical delivery | Unknown | No exhaustive client contract has been accredited |
| Overall functional completion percentage | Unknown | Cannot be calculated from scenario pass counts |

The previous verification ledger records **0 explicitly accredited complete semantic spells and 0 complete client spells**. Those are certification counts under its strict evidence schema, not an assertion that the implementation is 0% functional. Its execution and installation observations are historical and are deliberately not refreshed or promoted by this inventory.

## How to use the inventory

[JSON](class-dependency-coverage-20261007.json) contains the complete per-spell dependency rows and reverse indices. [CSV](class-dependency-coverage-20261007.csv) contains a compact review table. Rebuild with:

```sh
python3 server/tools/build_class_dependency_inventory.py
```

Start with `family_dependents` and `condition_dependents`. For each shared mechanism, record its native contract, actual runtime producer, relevant automated evidence and missing semantic domains. Then propagate only that specific proved contract to its dependent spells. A registered handler is a route; the handler can still reject missing native context, omit a phase, or require a configuration flag. Passing one spell cannot automatically certify every dependent spell.

All 813 combined spell-plus-innate closures contain at least one family that the static route inventory does not find registered. **This does not mean all 813 spells fail.** In particular, family 1099 appears through shared innate branches; native false guards and legal conditions can prevent structural nodes from executing. The inventory preserves those nodes and does not execute conditions. Likewise, the three historical unresolved states 759, 7986 and 8873 remain structural dependencies where applicable; the separate conservative native guard review explains why they disappear when constant-false branches are folded.

## Remaining coverage dimensions

The compact graph classifies child edges and reference producers 304/state, 315/area, 649/grant and 307/summon. It does not provide an exhaustive class-mechanic specification. Events, subscription priorities, execution counts, normal/critical transitions, removal and persistence, target flags, area occupancy, transformations and replacement producers, boundary parameter domains, deck/build combinations and complete summon abilities need richer exports and explicit contracts. Their status is `unknown`, not implicitly complete or not applicable.

Each row distinguishes a source registration from semantic/client verification. `historical_ledger_claims` preserves the old claims without accrediting them. Conditions have an explicit unknown contract status; event and class-mechanic semantics remain unknown. Absence of a classified area or summon edge is reported as `not_observed_in_classified_graph`, which does not certify non-applicability.

The tool hashes its compact graph, historical ledger, innate catalog, registry, runtime factory, dispatcher and arithmetic family declarations before and after the build. The generated report confirms those inputs stayed stable during this build. The graph itself is the earlier native structural snapshot; the report does not claim the running server or every current catalog was inspected. No runtime catalog, database, client process, Docker operation or service was used.

## Updated mechanism evidence

The [shared mechanism evidence ledger](class-mechanism-evidence-20261007.md) separates native export/publication, implementation, unit checks, offline runtime audits and manual client acceptance. The dependency rebuild now follows actual published summon profile ability references. It does not replace the older staged graph with an exhaustive current native mechanic specification. The tracked inputs and build tool stayed stable during the rebuild.
