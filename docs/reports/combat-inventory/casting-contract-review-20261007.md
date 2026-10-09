# Casting contract inventory — 2026-10-07

Offline static contracts; groups are overlapping, not gameplay pass/fail counts.

Reviewed 4143 native definitions, 722 class baselines and 722 class inventory records.

| Shared contract group | Native definitions | Class spells | Active class spells | Classes |
|---|---:|---:|---:|---|
| baseline_missing_levels | 6 | 0 | 0 |  |
| baseline_missing_range_modifiable | 4143 | 722 | 383 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 19 |
| baseline_zero_maximum | 1145 | 343 | 23 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 18, 19 |
| class_baseline_level_count_differs | 722 | 722 | 383 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 19 |
| conditional_line_of_sight_varies | 59 | 22 | 22 | 4, 5, 9, 11, 12, 16, 18, 19 |
| conditional_linear_varies | 33 | 28 | 28 | 1, 5, 14, 16, 18, 19 |
| conditional_missing_range_modifiable | 369 | 225 | 225 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 18, 19 |
| conditional_range_varies | 216 | 153 | 153 | 1, 3, 5, 6, 7, 8, 9, 12, 14, 15, 16, 18, 19 |

Missing range-modifiable metadata blocks a faithful general range resolver. Conditional variation identifies where baseline-only validation can disagree with the selected native table; it does not assert that every branch is reachable in every deck.

Use one complete casting-table selector for ordinary and granted spells, followed by the native live-actor range calculation. Keep zero-range and unmodifiable spells explicit. Implement and verify shared contracts before investigating individual spell behavior.

All impacted spell IDs and source SHA256 hashes are in the adjacent JSON. Regenerate with `python3 server/tools/audit_casting_contracts.py`. No runtime state is accessed.
