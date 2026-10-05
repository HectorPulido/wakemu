# Cotejo de código — 20

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**Filtra jugadores por mapa/instancia y retorna si no hay ninguno. Eso limita movimiento, pero no es una política completa de reproducción, envejecimiento o suspensión del mundo.**

Función `wander_location`, línea 68 de [server/wakfu_server/maps/monster_wander.py](../../../server/wakfu_server/maps/monster_wander.py). SHA-256: `4bfdd278846dd9e878d5c0fdb55e36e911bd6d810f83c434c4a684cd9c781ec7`.

```python
def wander_location(
    groups,
    map_id,
    instance_id,
    players,
    valid_edges,
    emit,
    *,
    occupied=(),
    radius=20,
    rng=None,
    excluded_ids=()
):
    """Serialize claim/move/broadcast using the same registry lock.

    emit(opcode,body) targets this map/instance; no session sender needed.
    Call at an explicit few-second interval, not on every server idle tick.
    """
    players = [
        p for p in players if (p["map_id"], p["instance_id"]) == (map_id, instance_id)
    ]
    if not players:
        return []
    moved_keys = []
    with groups.lock:
        roster = groups.available(map_id, instance_id)
        blocked = set(occupied)
        for group in roster:
            if any(m["id"] in excluded_ids for m in group["members"]):
                continue
            others = {
                point(m)
                for g in roster
                if g["key"] != group["key"]
                for m in g["members"]
            }
            result = plan(
                group["members"],
# Fragmento truncado; consultar la función completa en el enlace.
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/local_game_server.py](../../../server/local_game_server.py) | edbb31c2577a | `known_transports` L99, `position_lease_active` L114, `flush_positions` L128, `flush_position_batches` L144, `pack_text` L210, `realms_local` L215, `fixture` L269, `character_list_local` L282, `player_template` L293, `write_records` L322 |
| [server/wakfu_server/maps/planting_runtime.py](../../../server/wakfu_server/maps/planting_runtime.py) | 5247374d25ce | `state_packet` L260, `growth_schema` L274, `monster_growth_member` L282, `__init__` L16, `begin` L35, `cancel` L102, `complete` L113, `snapshots` L145, `mature` L155, `publish_growth` L216 |
| [server/wakfu_server/combat/combat_group_store.py](../../../server/wakfu_server/combat/combat_group_store.py) | db0407215064 | `__init__` L15, `_members` L38, `register` L41, `snapshot` L69, `available` L80, `claim` L93, `finish` L116, `release_session` L134, `respawn` L155, `recover_reservations` L170 |
| [server/wakfu_server/storage/world_scheduler.py](../../../server/wakfu_server/storage/world_scheduler.py) | 14bcec582737 | `__init__` L22, `keys` L26, `claim` L34, `renew` L48, `finish` L55, `__init__` L74, `claim` L82, `renew` L98, `finish` L108, `__init__` L120 |
| [server/wakfu_server/maps/world.py](../../../server/wakfu_server/maps/world.py) | b41d86cdcc95 | `__init__` L6, `location` L14, `snapshot` L17, `_send` L24, `join` L34, `leave` L46, `update` L57, `broadcast` L69, `emit_location` L80 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Definir zona y presencia | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Crear bootstrap idempotente | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Unificar reloj activo | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Activar de manera eficiente | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Integrar combate y siembra | Propuesta; requiere cambio, prueba y revisión del contrato |
| 6. Recuperar presencia y mundo | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
