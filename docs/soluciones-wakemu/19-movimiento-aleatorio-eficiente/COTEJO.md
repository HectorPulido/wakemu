# Cotejo de código — 19

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**El plan elige entre movimientos válidos de un paso, sin tirada previa del 25 %. Recorre aristas por grupo; la propuesta requiere índice compartido y decisión independiente.**

Función `plan`, línea 30 de [server/wakfu_server/maps/monster_wander.py](../../../server/wakfu_server/maps/monster_wander.py). SHA-256: `4bfdd278846dd9e878d5c0fdb55e36e911bd6d810f83c434c4a684cd9c781ec7`.

```python
def plan(members, players, valid_edges, *, occupied=(), radius=20, rng=None):
    if not members or radius <= 0:
        return None
    origins = [point(m) for m in members]
    if not any(
        max(abs(p["x"] - o[0]), abs(p["y"] - o[1])) <= radius
        for p in players
        for o in origins
    ):
        return None
    blocked = set(occupied) | {point(p) for p in players}
    edges = set((tuple(a), tuple(b)) for a, b in valid_edges)
    candidates = []
    for a, b in edges:
        if a != origins[0]:
            continue
        delta = tuple(y - x for x, y in zip(a, b))
        destinations = [tuple(x + d for x, d in zip(o, delta)) for o in origins]
        if len(set(destinations)) != len(destinations) or any(
            d in blocked for d in destinations
        ):
            continue
        if any((o, d) not in edges for o, d in zip(origins, destinations)):
            continue
        try:
            packets = [
                movement_packet(m["id"], o, d)
                for m, o, d in zip(members, origins, destinations)
            ]
        except ValueError:
            continue
        moved = deepcopy(list(members))
        for m, d in zip(moved, destinations):
            m.update(zip(("x", "y", "z"), d))
        candidates.append(dict(members=moved, packets=packets))
    return (rng or random).choice(candidates) if candidates else None
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/maps/monster_wander.py](../../../server/wakfu_server/maps/monster_wander.py) | 4bfdd278846d | `point` L13, `movement_packet` L17, `plan` L30, `wander_location` L68 |
| [server/local_game_server.py](../../../server/local_game_server.py) | edbb31c2577a | `known_transports` L99, `position_lease_active` L114, `flush_positions` L128, `flush_position_batches` L144, `pack_text` L210, `realms_local` L215, `fixture` L269, `character_list_local` L282, `player_template` L293, `write_records` L322 |
| [server/wakfu_server/combat/combat_groups.py](../../../server/wakfu_server/combat/combat_groups.py) | 20b42e0631d0 | `__init__` L12, `register` L17, `available` L43, `claim` L51, `finish` L63, `release_session` L73, `respawn` L82 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Precisar unidad y rango | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Indexar geometría y ocupación | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Sortear una decisión por ciclo | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Planificar ruta válida | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Emitir secuencia multi-paso | Propuesta; requiere cambio, prueba y revisión del contrato |
| 6. Medir distribución y CPU | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.

## Comportamiento comprobado

[Intervalo global, ausencia de tirada y codec de un paso](REVISION-RESPUESTAS.md).
