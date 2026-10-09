# Passive trigger-selector review

## Selector contract

`HasState` and `HasStateFromLevel` now accept the actor selectors `caster`, `target`, `casterController`, `triggeringCaster`, and `triggeringTarget`, case-insensitively. Runtime resolution uses the actual event relationship and only treats a registered native fighter (`eHg`) as an actor. A known null or a registered non-fighter area PV evaluates as false, matching the native `eII` actor lookup. Missing relationship or identity authority remains unknown and rejects evaluation. `eventTarget` remains unsupported because no producer for that relationship is available.

The focused regression batch passed 59 tests:

```sh
PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_conditions test_combat_runtime_adapter test_combat_casting_alignment test_combat_qi_snapshot
```

Coverage includes trigger aliases and levels, missing versus known-null relationships, area PV exclusion, static linear/diagonal casting alignment and Java integer behavior, plus QI `Z` mask aliases and signed-int coordinate overflow.

## Passive 8152

The focused offline audit of Sadida passive 8152, `Crecimiento Acelerado`, ran at legal level 10 with a complete trace and stable source hashes. It installed the passive and observed its internal cycle, but no activation. The attempted own cast (spell 915) was rejected as outside native range. The case is therefore not gameplay-verified. Full machine-readable output, including before/after source manifests, is in [passive-trigger-selector-review-20261007.json](passive-trigger-selector-review-20261007.json).

An earlier attempt during concurrent edits changed three runtime source files and was marked unstable by the audit tool; its counts were not used. The final report above was produced after those files were frozen and has `source_stable: true`.
