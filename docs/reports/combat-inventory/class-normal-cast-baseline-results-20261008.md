# Completed 18-class normal-cast baseline

The completed offline report `.runtime/combat-review-20261008/class-normal-casts-all18-01.json` records `finished=true`, `source_stable=true`, `normal_tool_stable=true` and 73/73 `ready_started` cases. Every expected direct spell/level pair was observed: 635 unique pairs across all 18 classes at levels 20 and 200, with no duplicate normal observations.

| Baseline outcome | Unique normal spell/level pairs |
| --- | ---: |
| Prepared transaction | 583 |
| Bounded target search found no eligible context | 33 |
| Effect transaction rejected | 6 |
| Target authority unresolved | 13 |
| Ready or owned turn not reached | 0 |

Preparation coverage is 91.811% of this baseline denominator. It is not a percentage of complete gameplay functionality. Representative commits were selected for 85 unique normal pairs and all 85 passed; the remaining 498 prepared pairs have no successful commit evidence in this report. Conditional state variants, optional passive variants and every class mechanic remain separate validation obligations.

Actual Ready grants produced 262 observations covering 130 unique available spell/level pairs. The other 132 observations repeat those grants across legal deck chunks and do not increase the 635-pair normal denominator.

The source report is preserved as evidence from its frozen source snapshot. Subsequent IsBreed null-target corrections do not retroactively change its 13 unresolved normal pairs. That fix addresses three recorded normal pairs (1535 at levels 20/200 and 7086 at level 200) by reproducing native `eNs` null-selection false; current runtime revalidation is still required.

The derived priorities report classifies family 341's nonpositive probability pool as `native_random_pool_context_invalid`. Native `eXR` calls `GS.ne(total)` without an empty-pool success branch; all thirteen conditional children of group 359670 require actual states 7961–7973 plus deck/effect/table-turn predicates. This remains a failed baseline preparation requiring genuine prerequisite execution, not a successful no-op or weakened random guard.

Reproduce the lightweight classification without loading combat catalogs:

```sh
python3 server/tools/summarize_class_normal_casts.py \
  .runtime/combat-review-20261008/class-normal-casts-all18-01.json \
  .runtime/combat-review-20261008/class-normal-casts-all18-01-priorities.json
```

The derived report includes the input SHA-256, unique affected pairs, class spread, normal/grant origins, rejection stages and separate context counts. It ranks actual implementation/authority failures separately from legal negative and prerequisite-context outcomes.
