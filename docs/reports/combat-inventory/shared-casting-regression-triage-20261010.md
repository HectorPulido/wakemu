# Shared casting regression triage — 2026-10-10

This review follows `.runtime/full-regression-20261010/server-tests.log` and fresh focused runs against the current pinned catalog. It does not treat a historical full-suite failure as proof that current live class casting is broken.

## Native LOS and casting fixture corrections

`combat_los.static_visible` now delegates to the original Sf raster program over complete `native-los-topology` columns when available. The older exported adjacent-pair catalogs remain a fallback only. Therefore the old tests' missing-map9 and unknown-distant-map1385 assumptions no longer hold. Missing actual surfaces return false through the native program; an unevaluated old pair is not the authority for a map with complete columns. Focused tests preserve native program delegation and the existing positive/blocked rays.

`authoritative_visible` requires actual source/target positions and signed native heights for its cast-height probes. The map1385 synthetic actor fixture omitted both fields. The correction supplies explicit positions and height6 rather than weakening runtime validation.

The self-cast fixture omitted the caster's explicit fight-property snapshot in the AP-cost context and the native rule's `range_modifiable` field. Both are now supplied; the real QI256 intermediate blocker, range, occupied-cell and resource assertions remain.

The general casting fixture supplied no `adapter.condition` provider despite exercising native cell criteria. In particular spell7551 has the actual criterion `(GetAlliesCountInRange(2, "target") - 1) >= 1`. Its legal positive fixture now registers a real ally, resolves the true cell/actor aliases and uses the shared `RangeFighter`/`range_count` implementation. The expression is neither removed nor forced true. LOS rejection now uses an actual QI256 blocker; the legacy callback is not the shared native eligibility consumer.

The cast-facing rollback fixture's mocked plan predated `extra_resource_deltas`. It now supplies an explicit empty mapping, allowing the original downstream dispatcher failure and source-position/resource rollback assertions to execute.

## Legacy adjacent executor

The two `test_combat_execute` errors enter `execute_adjacent_cast`, a bounded old executor that does not provide the current required conditional casting authority. Do not invent empty authority or revive this path merely to turn its historical tests green.

Repository search:

```sh
rg -n 'execute_adjacent_cast\(' server --glob '*.py'
rg -n 'execute_adjacent_cast' server/local_game_server.py
```

The first command identifies only the definition in `combat_execute.py` and calls in `test_combat_execute.py`. The second identifies an unused import in the opcode13260 branch. Current class casts there call `prepare_server_spell`, then commit the actual shared transaction. Thus these legacy errors are documented API drift, not evidence that current class spell dispatch uses the failing executor.

## Validation boundary

Fresh focused reruns are coordinated with the shared test owner. Syntax compilation and scoped diff whitespace checks passed. The fresh current-source four-module run passed23/23. No production source changes, server restart or deployment are part of this review.
