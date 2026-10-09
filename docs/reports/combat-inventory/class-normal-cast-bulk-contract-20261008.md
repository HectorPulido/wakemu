# Bulk normal class-cast baseline

`server/tools/audit_class_normal_casts.py` inventories every available direct class spell at levels 20 and 200, covering all 18 class IDs. The current source yields 635 spell/level pairs in 73 legal deck chunks: eight active slots at level 20 and twelve at level 200. No spell is inserted into an unavailable slot or bypasses ordinary packed-UID/deck ownership.

Each chunk runs the existing production Ready path with actual innate initialization and native start events, then advances a private runtime through actual turn/ack handlers until the owned PC can act. All casts start from that initialized turn baseline. Available native grants and any installed transformation book are recorded separately from the ordinary deck denominator. The default NPC fixture uses its real source profile/level bounds and native QI terrain indices; it has no invented HP or casting authority.

Candidate selection uses `eligible_cast_targets`, which invokes the production ownership, cost, criterion, usage, range, terrain and LOS validator. The default bounded search checks up to 32 cells and previews at most two eligible targets. Bounded exhaustion, a known legal rejection and missing authority remain distinct. A spelling or `ValueError` message alone is not treated as proof of a legal negative.

Each accepted candidate executes the production effect transaction against the unchanged baseline. Representative transactions additionally commit on a private RuntimeMessages clone when a new actually completed effect family is observed, or for the first successful representative of a class/level. Commit packet serialization, source snapshot matching and plain-JSON checkpoints are exercised. Branches are explicitly independent, rather than a fabricated shared spell sequence or resource reset.

The optional `--commit-each-prepared` mode instead commits every prepared
candidate, each in a fresh private clone of the same actual Ready/turn baseline.
The default representative policy is unchanged. Each full-mode attempt records
its `commit` result, actual delivered and prepared-effect opcode counts, planned
native costs, before/after resource values, state ledgers and the plain-JSON
checkpoint hash. Net resource changes include spell effects as well as payment;
they are not represented as cost-only deltas. Neither successful nor partially
failed commit branches are published into the baseline.

The report retains the first failed native effect and original exception chain, source hashes before/after, source rollback checks, complete per-class active inventory, dynamic grant availability, and grouped first root failures. Preview success, commit success and complete graphical gameplay are separate results. Optional passive deck variants and all conditional class scenarios remain outside this baseline's completion claim.

`numeric_summary.normal` uses exactly the 635 direct spell/level pairs as its denominator. Its preparation partition distinguishes prepared transactions, effect rejection, a complete legal search with no context, bounded search exhaustion, unresolved target authority, other access/authority errors, and entries never reached through Ready/turn initialization. Commit-selected, commit-passed and commit-rejected counts are independent; a prepared transaction cannot hide a failed commit. Mixed commit outcomes are counted explicitly. `numeric_summary.grants` counts distinct spell/level availability and repeated observations across deck chunks separately, excluding them from the normal denominator. The prepared percentage is a reproducible baseline metric, not a global functional percentage.

## Serialized execution

Run one focused smoke before the bulk job, under the coordinated catalog-memory slot:

```sh
PYTHONPATH=server:server/tools /tmp/wakemu-combat-review-venv/bin/python3 server/tools/audit_class_normal_casts.py .runtime/combat-review-20261007/class-normal-casts-smoke-01.json --breeds 9 --levels 20 --candidate-limit 16 --maximum-eligible 1
```

Then run the single bulk process, with one prewarmed catalog load:

```sh
PYTHONPATH=server:server/tools /tmp/wakemu-combat-review-venv/bin/python3 server/tools/audit_class_normal_casts.py .runtime/combat-review-20261007/class-normal-casts-01.json
```

No service, socket, database, client or AI mutation is part of either command. Source changes during a run invalidate its source-stable evidence flag and must be reported as such.

After shared fixes and the focused tests are source-stable, the full commit
mode can close the preparation-only verification gap with one bulk process:

```sh
PYTHONPATH=server:server/tools /tmp/wakemu-combat-review-venv/bin/python3 server/tools/audit_class_normal_casts.py .runtime/combat-review-20261008/class-normal-casts-all-commits-01.json --commit-each-prepared
```

`prepared_attempts_without_commit` counts the actual prepared normal attempts
with no selected commit. It is separate from spell/level pairs without a
successful commit, which also include rejected commit attempts. Full-mode
outcomes still prove only the enumerated baseline targets and criteria, not all
conditional gameplay or graphical client behavior.

## Verification status

`PYTHONPATH=server:server/tools:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_class_normal_cast_inventory`: three pure tests passed in 0.004 seconds. They verify full 18-class/36-level inventory partitioning, legal native slot/deck limits, and root-failure classification from real exception types and explicit production rejection fields. Tool and compatible optional Ready-provider hook pass AST parsing. Actual production smoke and bulk results are pending the coordinated validation job.

Four additional light regressions cover representative versus every-prepared
selection, independent successful branch bookkeeping, rejection without partial
publication, and attempt counts without inflating the spell/level denominator.
Their serial validation is queued; source compilation passed. No all-commit bulk
result is claimed before that run finishes.
