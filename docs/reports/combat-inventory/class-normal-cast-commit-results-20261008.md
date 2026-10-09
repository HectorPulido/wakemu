# All-class normal cast and commit results — 2026-10-08

Scope: ordinary owned class decks, baseline innates, levels20/200, all18 classes. This audit does not certify every state-dependent table, passive, summon interaction or client presentation.

## Frozen execution

Report: `.runtime/combat-review-20261008/class-normal-casts-all18-commiteach-02.json`.
SHA256: `ed9ddde6975709594f88d96d73524971a1cfc0e9ce357b050f753cbeebe846bc`.
Actual execution snapshot: `luna-normal-casts-all18-commiteach-02`. The680 recorded input hashes agree before/after execution and with the snapshot manifest.

All73 Ready profiles passed across36 breed/level groups. There are635 distinct ordinary spell/level pairs:557 prepared and committed,43 bounded searches without an eligible context,32 effect-transaction rejections and3 unresolved target-authority predicates. No prepared pair failed its commit. The971 actual commit attempts do not increase the distinct-pair denominator. Grants are130 distinct pairs, observed262 times, and stay separate.

The basic preparation-and-commit rate is87.717%. No global gameplay percentage follows from this denominator.

## General blockers before individual spell work

| Shared route | Rejected pairs | Current next gate |
| --- | ---: | --- |
| State application304 |22| Source-qualified HP0/native target-life correction:19 focal state/resource tests pass; replay actual affected class casts |
| Resource loss48/55 |4| Same qualified target-life correction; replay actual affected casts |
| Displacement300 |3| Original null/carried recipient no-op order restored; refreshed59-test conditions/QI/displacement batch passes; actual cast replay pending |
| HP setter16/QI lifecycle |2| Complete native raw-HP authority preserves still-IN_PLAY actors; actual cast replay pending |
| Dispel421 |1| Original client-only flag3 and null recipient semantics corrected; focal and actual replay queued |

The three unresolved predicates belong to Eni1535(levels20/200) and Zobal7086(level200). A later scoped IsBreedId replay covers70 pairs, commits62 and resolves all three unknowns into bounded searches with no eligible context. This proves the predicate correction, not a positive resurrection sequence.

## Comparison with historical preparation baseline

The earlier report prepared583 pairs and committed only85 selected pairs. The same635 keys are present in both reports. Thirty-one previously prepared pairs now reject, five previously rejected pairs now prepare, and ten unresolved predicates become bounded searches. The net preparation change is−26. Eighty-two of653 common input hashes changed between those reports; without a controlled isolation, this difference cannot be attributed to a single patch.

General corrections are checked against actual affected casts before scheduling another full all-class run. A negative prerequisite remains separate from a missing implementation. The complete inventory and client acceptance requirements remain in [current status](current-status-20261008.md) and the [manual plan](manual-representative-acceptance-20261008.md).
