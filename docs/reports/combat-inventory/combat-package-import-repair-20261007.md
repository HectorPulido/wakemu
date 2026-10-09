# Combat package import repair

The package refactor left combat modules importing sibling modules which now
live in the parent package or its `items`, `characters`, and `maps` packages.
For example, `combat_damage_healing` imported `.equipment_damage`, although
the sole source module is `wakfu_server/items/equipment_damage.py`. This
prevented even a small standalone import of common damage arithmetic.

The repair changes unresolved relative imports only when the module name has
one unique source under `wakfu_server`. Six equipment-damage imports were
corrected first; the subsequent AST inventory corrected 61 combat files with
other unresolved imports. Existing valid combat-relative imports were left
intact. No module was duplicated and no game behavior was changed.

Validation: Python `compileall` passes for the combat package. Direct imports
of `combat_damage_healing`, `combat_damage_parameters`,
`combat_force_characteristic`, `combat_life_steal`, `combat_actor_snapshot`,
and `combat_stat_effects` pass without starting services or loading the full
spell catalog. Broader snapshot validation is delegated to the validation
agent; compilation alone does not certify all runtime import paths.
