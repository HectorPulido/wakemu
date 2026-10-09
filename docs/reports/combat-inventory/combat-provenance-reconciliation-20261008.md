# Combat report provenance reconciliation

This stdlib audit compares recorded report inputs with snapshot manifests. Running from the live worktree does not automatically invalidate a report when its recorded inputs match the captured source. Conversely, a captured snapshot alone does not establish that the process executed from it. Semantic denominators and test outcomes remain frozen.

| Scope | Snapshot | Before matched / missing / different | After hashes | Tool evidence |
|---|---|---|---|---|
| normal635 | luna-normal-casts-smoke-01 | 653 / 0 / 0 | {'matched': 653, 'missing': 0, 'different': 0} | tool_sha256:matched, normal_tool_sha256:matched |
| passive339 | luna-passive-fast-01 | 671 / 0 / 0 | {'matched': 671, 'missing': 0, 'different': 0} | tool_sha256:matched, source_tool_sha256:matched |
| semantic42 | luna-semantic-next-01 | 677 / 0 / 0 | {'matched': 677, 'missing': 0, 'different': 0} | tool_sha256:matched, source_tool_sha256:matched |
| Enutrof17 | luna-enutrof-passive-replay-02 | 674 / 0 / 0 | {'matched': 674, 'missing': 0, 'different': 0} | tool_sha256:matched, source_tool_sha256:matched |
| M2 | luna-cra-precision-05 | 531 / 0 / 0 | not recorded separately | not recorded |
| M3 | luna-m3-retirement-01 | 529 / 0 / 0 | not recorded separately | not recorded |
| M7 | luna-m7-m10-01 | 642 / 10 / 14 | {'matched': 642, 'missing': 10, 'different': 14} | tool_sha256:missing, audit_tool_sha256:matched |
| M10 | luna-m7-m10-01 | 642 / 10 / 14 | {'matched': 642, 'missing': 10, 'different': 14} | tool_sha256:missing, audit_tool_sha256:missing |
| resource923 | luna-resource923-01 | 678 / 0 / 0 | {'matched': 678, 'missing': 0, 'different': 0} | tool_sha256:matched |
| copy_rawfix | luna-copy-8559-rawfix-01 | 677 / 0 / 0 | {'matched': 677, 'missing': 0, 'different': 0} | tool_sha256:matched |
| Recall13 | luna-recall-retired-slot-13 | 680 / 0 / 0 | {'matched': 680, 'missing': 0, 'different': 0} | tool_sha256:matched, audit_tool_sha256:matched, recall_callback_tool_sha256:matched |
| Microbot02 | luna-microbot-rail-lifecycle-02 | 537 / 0 / 0 | not recorded separately | not recorded |
| Sram_double_death01 | luna-sram-double-lifecycle-01 | 679 / 0 / 0 | {'matched': 679, 'missing': 0, 'different': 0} | tool_sha256:matched |
| copy_book_final | luna-copy8559-lifecycle-final-03 | 679 / 0 / 0 | {'matched': 679, 'missing': 0, 'different': 0} | tool_sha256:matched |

[Detailed identities, missing paths and divergences](combat-provenance-reconciliation-20261008.json). Relative module paths resolve by a unique manifest path suffix; bare module filenames resolve only when the manifest basename is unique. The normal635 mapping is byte-confirmed by validation; the hash-based M3 snapshot candidate is explicitly provisional until execution mapping is confirmed. Missing tool or after hashes are unknown evidence, not automatically test failures.

Cinetosis formula-final07 was reported source-unstable with nine source edits and cannot certify a frozen formal suite. The subsequent snapshot08 log records 5 tests PASS and stable source, with validation attesting execution inside snapshot07; it has no published per-input hash map and is recorded separately. The unstable earlier run remains historical; this does not invalidate unrelated stable reports. Current client verification and full mechanic coverage are not implied by provenance matches.
