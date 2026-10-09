# Placement reconstruction discarded selected terrain authority

A fresh map527 fight rejected teleport with `Teleport requires actual native selected-surface provenance`. Map527 already exists in the published 934-map native Vy catalog; this was not a missing export.

Actual encounter path: `local_game_server` calls `local_arena`, then `combat_placement_policy.freeze`, then `create_placement`. `local_arena` supplied selected native surface indices and manifest provenance. `freeze` reconstructed its first and repeated layouts through `_arena`; that helper called `combat_wire.arena` without indices and omitted provenance. Thus every selected surface reverted to index zero, and bootstrap had no provenance to retain.

The shared `_arena` now resolves each saved selected altitude against the first native chunk's ordered Vy surfaces, requires a unique matching altitude/index in the low-six-bit domain, supplies those indices when regenerating wire masks, and carries published provenance into bootstrap. Both first creation and retry use the same producer. Legacy failed maps remain explicit failures. No live mask attestation or replacement was performed.

This closes the shared selected-surface authority used by teleport and throw. It does not claim all displacement behavior: cardinal forced movement still has its independent native transition policy.

Validation: `PYTHONPATH=server .runtime/local/verification-venv/bin/python -m unittest discover -s server/tests -p test_combat_placement_surface_authority.py` — 2 tests passed. Nonzero selected index survives first/retry reconstruction with provenance; native map decode failure rejects without fallback. No database or service operation.
