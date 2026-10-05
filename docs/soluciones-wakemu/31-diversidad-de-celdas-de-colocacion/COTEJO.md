# Cotejo de código — 31

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**El generador debe cotejarse con conectividad y terreno antes de variar celdas. Aleatoriedad sin invariantes puede producir equipos inaccesibles o solapados.**

Función `generate`, línea 31 de [server/wakfu_server/combat/combat_placement_cells.py](../../../server/wakfu_server/combat/combat_placement_cells.py). SHA-256: `d069d334ddc6c5795030a57d6d38458621c7e3451afe0374705af4f5cbedaa20`.

```python
def generate(cells, edges, seeds, *, slots_per_team=6):
    """Return disjoint team0/1 placement sets containing every current actor.

    Native outgoing paths choose nearby candidates; enemy seed cells are blocked
    during that search. Small maps yield their available capacity, never fake
    slots. More than six actors retain all their occupied seed cells.
    """
    if type(slots_per_team) is not int or not 1 <= slots_per_team <= 127:
        raise ValueError("Invalid local placement capacity")
    cells = {_cell(cell) for cell in cells}
    if not cells or len({cell[:2] for cell in cells}) != len(cells):
        raise ValueError("Placement needs selected unique-height terrain")
    if not isinstance(seeds, dict) or set(seeds) != {0, 1}:
        raise ValueError("Both placement teams require actor seeds")
    selected = {team: {_cell(seed) for seed in group} for team, group in seeds.items()}
    if (
        any(not group or not group <= cells for group in selected.values())
        or selected[0] & selected[1]
        or sum(map(len, selected.values())) > 127
    ):
        raise ValueError("Placement actor seeds overlap or are unavailable")
    outgoing = defaultdict(set)
    for raw in edges:
        if not isinstance(raw, (tuple, list)) or len(raw) != 2:
            raise ValueError("Invalid placement terrain edge")
        origin, target = map(_cell, raw)
        if (
            origin not in cells
            or target not in cells
            or abs(origin[0] - target[0]) + abs(origin[1] - target[1]) != 1
        ):
            raise ValueError("Placement edge is outside native selected terrain")
        outgoing[origin].add(target)
    distances = {
        team: _distances(selected[team], cells, outgoing, selected[1 - team])
        for team in (0, 1)
    }
    candidates = {
# Fragmento truncado; consultar la función completa en el enlace.
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/combat/combat_placement_cells.py](../../../server/wakfu_server/combat/combat_placement_cells.py) | d069d334ddc6 | `_cell` L9, `_distances` L19, `generate` L31 |
| [server/wakfu_server/combat/combat_arena_selection.py](../../../server/wakfu_server/combat/combat_arena_selection.py) | eb8ac0198e19 | `_cell` L10, `_reachable` L26, `bounded_arena` L41 |
| [server/wakfu_server/combat/combat_bootstrap.py](../../../server/wakfu_server/combat/combat_bootstrap.py) | ff43dba3aa3a | `placement_positions` L12, `placement_messages` L23, `player_payload` L109, `create_placement` L134, `target_position` L243 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Distinguir determinismo de defecto | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Definir política de formación | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Elegir una vez bajo versión | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Asignar cupos y casos pequeños | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Medir diversidad y legalidad | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
