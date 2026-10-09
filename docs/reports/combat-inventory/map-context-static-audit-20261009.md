# Map context and terrain static audit

The attached AST census checks every Python file under `server` for direct `fight.map_id` and `fight.instance_id` attribute accesses. The semantic review covers placement, QI surfaces/occupation, LOS, terrain preview snapshots, durable checkpoints and reconnect serialization. It does not certify all maps, elevations or live reconnect behavior.

## Concrete fix

`combat_cell_group.native_cell_group_population` required `fight.map_id`, although ordinary `Fight` does not define it and bootstrap installs the map identity in `native_qi_surface_provenance`. This could reject family349 class effects after legitimate Ready or restoration. The consumer now validates that persisted provenance against the selected surface source and loads that exact map. It does not accept an incidental `map_id` fixture attribute as authority. Two pure regressions cover a non1134 map without that attribute and missing/stale provenance rejection.

## Remaining priorities

1. **Qualify LOS actor lifecycle parity.** `combat_los.authoritative_visible` builds required footprints and source/target actor lookup using `hp > 0`. `combat_qi_fight.current_registry` preserves explicit HP0 OFF_PLAY QI registrations until actual OUT_OF_PLAY removal. Production server callers use the LOS function. This is a real source divergence requiring exact native QI.h blocker and caller footprint qualification; it is not yet proof that every corpse must block. No guessed HP/lifecycle fix was applied.
2. **Audit fixture map identity.** Several standalone class audit callbacks still read raw `fight.map_id`; some fixtures manually assign1134. Their location census is preserved in JSON. This can conceal missing runtime contracts and prevents claiming general map support from those tools. Their owners should bind arena/session map or validated provenance rather than a hardcoded fallback.
3. **Map source availability remains a separate gate.** Native LOS topology validates map identity and complete XYZ coordinates, selected surface consumers validate provenance, and unknown exported rays reject explicitly. No count of all maps with complete sources was obtained from the migrated catalog in this source-only review.

## Existing contracts inspected

- Spectator occurrences are legitimate accesses to a separate `_Fight` dataclass declaring map/instance fields, not the combat `Fight` defect.
- Ordinary authority's `native_instance_id` is produced from source `map_id`; its name alone does not establish an instance/map mix-up.
- Bootstrap validates QI rectangle fields together, copies masks plainly, and compares selected-surface provenance with the arena map.
- Preview terrain uses immutable walkable/edge sets; durable checkpoint snapshot serializes all Fight fields, QI registrations and surface provenance through the plain-state validator. This avoids the missing map attribute being repaired merely by deepcopy, but does not prove all restore consumers.
- QI registration distinguishes retired actors, ordinary OFF_PLAY death and settled summon retirement; rebuilding occupation from living actors would discard that contract.

Validation: `PYTHONPATH=server /tmp/wakemu-combat-review-venv/bin/python -m unittest discover -s server/tests -p test_combat_cell_group_map_context.py` —2 PASS; same command with `test_combat_qi_snapshot.py` —7 PASS. No services, deployment, database access or AI changes.
