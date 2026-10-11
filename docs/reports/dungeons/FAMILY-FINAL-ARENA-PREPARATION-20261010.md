# Final family arenas with retained native exploration

Four previously blocked ordinary definitions use the explicit local fallback
requested by the user. These configurations are source-only; activation and boss
mechanics are not certified by this preparation.

| Dungeon | Local final encounter | Native final region gate depth |
|---|---|---:|
| Necromundo | Identified boss once; no ordinary native family available | 1 |
| Guarida de los Supervillanos | Four distinct identified bosses, once each | 1 |
| Mazmorra Riktus de Élite | Eight native family actors including identified boss | 2 |
| El Hammalmejil | Eight native family actors including identified boss | 1 |

Intermediate native regions contain no encounters. Every native physical gate is
retained and assigned to stage one, making it open on entry. The entire native
exploration geometry remains present. The combat room is restricted to a native
closed region at maximal gate-graph distance from arrival, with directed entry
reachability proved. All generated monster positions must lie inside that final
region. Six player placement slots and directed engagement are validated.

Native exterior exits are bound using literal objects and approach positions.
Riktus has equivalent native exit aliases with one identical exterior
destination; the deterministic representative and all aliases are recorded.
No exit destination or approach is fabricated.

This deliberately does not claim official room counts, intermediate encounters,
monster quantities or boss mechanics. Boss-only rosters preserve the actual
identified bosses instead of inventing family adds or duplicating bosses.

Reproduction: `PYTHONPATH=server python server/tools/prepare_family_final_arenas.py`
with the normal read-only published catalog connection. Results:
`FAMILY-FINAL-ARENA-CANDIDATES-20261010.json`; configurations:
`.runtime/local/family-final-arena-candidates-20261010/`.
