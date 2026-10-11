# Monster extraction validation

Date: 2026-10-10. All checks are offline. No client game session, database publication or service restart was part of this work.

## Automated regression tests

```sh
PYTHONPATH=server python3 -m unittest server.tests.test_monster_combat_extraction -v
```

Result: **13 tests passed**. They cover transitive spell/state/grant closure, cycles, missing definitions, duplicate monster references, conflicting effect definitions, preservation of opaque metadata, fixed spell levels versus actor-level sentinel `-1`, malformed initial-state triples, separate level-zero roots and references, deterministic gzip output and HMI process-local allocation IDs. A changed particle-system ID or another semantic difference remains a hard conflict. Additional checks prove that the compact dependency index produces the same closure as complete definitions, preserves semantic conflict detection, and that streaming gzip retains the exact JSON bytes with deterministic headers.

Python compilation and `git diff --check` also passed. The Java exporters compiled with the installed JDK 22.

## Installed-client extraction

The source bundle is under `.runtime/monster-combat-extraction-20261010`. Its 12 compressed source documents are checksum-pinned in `provenance.json`; derived inventory generation verifies all those hashes before use. The [review manifest](EXTRACTION.json) retains the source evidence without committing raw dumps.

Independent acceptance of this complete bundle passed: all 12 source checksums match, and all eight ordinary reference profiles resolve their owned spell roots and candidate dependencies. The receipt is `.runtime/monster-combat-extraction-20261010/acceptance.json`.

The final compact-index and streaming-compression improvements pass the 13 regression tests. A fresh end-to-end repeat under `.runtime/monster-combat-final-20261010` was stopped during state conversion because of host memory pressure; that partial directory is not a validated bundle. These improvements therefore have regression coverage, but no completed fresh extraction run. The original complete bundle above remains the extraction evidence. Existing shared converters still retain large native state graphs in memory.

| Evidence | Count |
|---|---:|
| Monster references | 2,874 |
| References with owned abilities | 1,934 |
| Distinct monster-owned spell references | 3,091 |
| Spell definitions after secondary-grant closure | 3,113 |
| Installed native casting definitions | 4,143 |
| Positive spell-tree effect definitions | 21,161 |
| State definitions | 6,129 |
| State effect definitions | 43,952 |
| Characteristic definitions | 92 |
| Monster characteristic profiles | 2,874 |
| Effect-area definitions | 1,436 |
| Effect-area tree definitions | 3,624 |
| Casting-root selector/collision records, including the zero-level supplement | 9,262 |
| References with initial states | 1,679 |
| Explicit zero-level ability records | 7 |
| References missing owned-ability casting tables | 0 |
| References missing owned-ability casting-root metadata | 0 |

The eight ordinary Miaumiau/Tofu/Jalató references in the overview have no missing candidate dependencies in the implemented traversal. The generated name-based review cohort contains 42 references, including quest/event/pet variants; names do not establish that every variant is an ordinary encounter mob.

## Explicit remaining boundaries

Thirteen references have unresolved candidate definitions in the conservative state/grant traversal. The review manifest records their identities and gap counts. These are not automatically confirmed missing gameplay definitions: dynamic reference semantics need investigation.

There are 1,121 owned ability records whose effective maximum level exceeds the 1–200 effect-parameter sample domain. Native casting tables at their available positive levels and raw effect curves remain preserved. A level-zero spell/effect supplement is available separately; it does not fill every possible state level or dynamic runtime context.

`runtime_status` remains `not_validated` throughout the inventory. The checks establish source extraction and structural integrity. They do not establish complete NPC execution, official AI behavior or client animation acceptance.
