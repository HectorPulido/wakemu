# Complete filtered monster inventory — 2026-10-11

Includes **1,921 unique native references**, across all levels and native roles. These are definitions, not deduplicated species. Excluded from every delivered list: **940 without owned spells and 13 with incomplete data**. Source total: 2,874.

Live catalog revision: `677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d`.

[Full CSV](ALL_MONSTERS.csv) · [Full JSON and summary](ALL_MONSTERS.json)

| Category | References | % of included inventory | List |
| --- | ---: | ---: | --- |
| Enabled | 247 | 12.86% | [CSV](ENABLED.csv) |
| All families covered; native execution unreviewed | 1,297 | 67.52% | [CSV](COVERED_UNREVIEWED.csv) |
| All families covered; execution or initialization pending | 112 | 5.83% | [CSV](PENDING_NATIVE_EXECUTION.csv) |
| All families covered; dependency import pending | 6 | 0.31% | [CSV](PENDING_DEPENDENCY_IMPORT.csv) |
| One effect family missing | 219 | 11.40% | [CSV](MISSING_ONE_EFFECT_FAMILY.csv) |
| Two or more effect families missing | 33 | 1.72% | [CSV](MISSING_MULTIPLE_EFFECT_FAMILIES.csv) |
| Special encounter or minigame exception | 7 | 0.36% | [CSV](ENCOUNTER_EXCEPTION.csv) |

## Meaning and limits

Covered families do not certify native imports, parameters, criteria, summons, constructors, AI or encounter prerequisites. One missing family is a smaller static gap, not a promise of low implementation effort. Multiple missing families do not imply a particular duration. The 247 enabled references match the running World policy; visual acceptance is separate.

Seven explicitly excluded trainer/racing actors remain marked as encounter exceptions. All other levels and native roles, including bosses and ultimate bosses, remain included. Native roles are recorded rather than guessed from names.

## Level breakdown

Bands use native **maximum level**, so ranges crossing boundaries are counted once.

| Native maximum level | Enabled | Covered, unreviewed | Execution pending | Import pending | One family missing | Multiple missing | Exceptions | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 1-9 | 57 | 23 | 5 | 0 | 7 | 5 | 7 | 104 |
| 10-49 | 190 | 0 | 107 | 6 | 21 | 6 | 0 | 330 |
| 50-99 | 0 | 373 | 0 | 0 | 36 | 4 | 0 | 413 |
| 100-149 | 0 | 371 | 0 | 0 | 60 | 4 | 0 | 435 |
| 150-199 | 0 | 245 | 0 | 0 | 27 | 6 | 0 | 278 |
| 200+ | 0 | 285 | 0 | 0 | 68 | 8 | 0 | 361 |

## Shared missing families

Counts overlap. Implementing a family reduces a static gap; it does not certify activation.

| Missing family ID | Affected included references |
| --- | ---: |
| 830 | 62 |
| 1021 | 49 |
| 994 | 42 |
| 207 | 25 |
| 328 | 20 |
| 327 | 19 |
| 21 | 9 |
| 1003 | 8 |
| 250 | 7 |
| 1041 | 6 |

## Cheap refresh

Rechecked all references with `server/tools/audit_monster_family_coverage.py --all`, using the existing extracted inventory and current handler registrations. Joined by native reference with `ACTIVATION_STATUS.json` and a read-only live NPC policy query. The coverage counts match the prior all-level report; no spell executions, database writes, service changes or restarts were performed.
