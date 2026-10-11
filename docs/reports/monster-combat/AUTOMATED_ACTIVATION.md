# Automatic native monster activation

The activation pipeline is level-independent. Static family coverage selects candidates; it does not authorize deployment. Every owned spell at every native actor level must produce a real native effect before the reference can be enabled. The entire native level range must fit the selected maximum; references spanning beyond it are excluded.

## Pipeline

`server/tools/automate_monster_activation.py` performs these fenced phases:

1. Verify native extraction provenance and coverage, export the selected dependency closure using the existing class spell exporter/converter, and merge without replacing existing definitions. Missing NPC state resistance metadata is exported with the existing native class getter/exporter and merged append-only; every existing class definition and attested absence must remain identical.
2. Preview every native actor-level/spell combination. Try enemy, self and empty cells, plus a native wounded-ally scenario for healing spells. Reject unsupported targeting, conditions and resource costs.
3. Reconstruct successful scenarios, verify an unchanged forecast source, force serialization failure and verify complete rollback, then commit through the real AI provider and serializer.
4. Run class, combat and activation regressions, with runtime/test/catalog hashes pinned across phases.
5. Finalize only references passing every gate. Preserve previously enabled references and all unrelated catalog documents.
6. Validate staging by default. `--stage` writes an **inactive** release. This tool does not switch the active catalog or restart services.

NPC initial-state triples retain native order, descriptor-relative level `-1`, and flags. The ordinary constructor runs on a private fight before QI actor insertion and publishes atomically. A reference with initial states additionally requires an exact constructor receipt in each effectful preview and in the committed AI delivery. Unsupported constructor branches remain pending.

## Run

Use the verification environment containing psycopg and native dependencies:

```bash
.runtime/local/verification-venv/bin/python server/tools/automate_monster_activation.py \
  --coverage docs/reports/monster-combat/ALL_LEVELS_COVERAGE.json \
  --bundle .runtime/monster-combat-extraction-20261010 \
  --output .runtime/monster-activation-run-NEW \
  --dsn 'host=127.0.0.1 port=15432 dbname=wakemu_runtime user=wakemu' \
  --password-file .runtime/local/secrets/postgres-password \
  --registry .runtime/e18-deploy-server/protocol/effect-characteristic-registry.json \
  --setters .runtime/monster-coverage-20261010/set-current.json \
  --max-level 9
```

The output directory must be new and beneath `.runtime`. Repeat `--only-ref ID` to restrict the cohort; this cannot bypass coverage or level eligibility. A higher `--max-level` uses the same pipeline, without changes to species-specific code. A stale extraction or handler inventory is rejected rather than silently reused. DSNs containing inline passwords are rejected; secrets never appear in command arguments or pipeline receipts.

After offline validation, publication and service deployment must preserve the complete current checkout and its catalog revision. Manual review follows the final deployed cohort, not the original static candidate list.

## Known limits

Some covered families still require additional native metadata or execution context. Examples are state resistance modes, missing runtime casting tables present in the extraction, cell-group metadata, native quest/race conditions, finite constructor timelines, insufficient native resources, and references that cannot form a living combat actor. These conditions are reported separately. Coverage is never used to invent missing data, inflate resources or bypass native legality.

## Current deployed result

The [2026-10-10 execution report](AUTOMATED_UNDER_10_20261010.md) records 10 newly enabled references from the 39 pending candidates, 40 enabled in total, 29 pending, and 461 passing selected checks. World and AI are verified healthy. Continue with the [manual acceptance sequence](MANUAL_PENDING_COHORT.md).

## Shared blocker investigation

The [pending-blocker investigation](BLOCKER_GENERALIZATION_20261010.md) documents the automatic resistance dependency export, native NPC spell maximum-level correction, and the next reusable cell-group and summon-profile imports. Two further references are validated in an inactive candidate; the live deployment remains at 40.
