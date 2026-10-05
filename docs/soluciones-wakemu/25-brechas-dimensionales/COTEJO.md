# Cotejo de código — 25

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**La interacción está restringida a tipos de transporte soportados. Ese resolver no ejecuta una sesión de brecha con oleadas, tiempos y recompensas; no clasificar una brecha como un simple teletransporte.**

Función `interaction`, línea 44 de [server/wakfu_server/maps/world_static.py](../../../server/wakfu_server/maps/world_static.py). SHA-256: `40311961155deb132313e7504c039989efd4acbbe53248998eb41543c3d035d1`.

```python
def interaction(character, body):
    """Decode cpF/12870 without treating every action as transport discovery.

    Classification is not permission to execute an action. Native access rules,
    owned state and action-specific responses must be validated by its handler.
    """
    if len(body) != 12:
        raise ValueError("Invalid interactive request length")
    identity, action, parameter = struct.unpack(">qHH", body)
    row = _MAPS.get(character["map_id"], {}).get(identity)
    if character.get("instance_id", 0) != 0 or row is None:
        raise ValueError("Unknown interactive object in current map instance")
    name = _ACTIONS.get(str(action))
    if name is None:
        raise ValueError("Unknown native interactive action")
    route = "unsupported"
    if row["type"] in ("Zaap", "Drago"):
        route = (
            "transport_registration"
            if name == "REGISTER"
            else "transport_menu"
            if name == "ACTIVATE"
            else "unsupported"
        )
    elif row["type"] == "Door":
        route = "door_state"
    elif row["type"] == "Teleporter":
        route = "teleporter"
    return {
        "id": identity,
        "type": row["type"],
        "action_id": action,
        "action": name,
        "parameter": parameter,
        "route": route,
        "map_id": row["map_id"],
        "x": row["x"],
        "y": row["y"],
# Fragmento truncado; consultar la función completa en el enlace.
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/maps/world_static.py](../../../server/wakfu_server/maps/world_static.py) | 40311961155d | `objects` L22, `snapshots` L27, `interaction` L44 |
| [server/wakfu_server/maps/generic_transports.py](../../../server/wakfu_server/maps/generic_transports.py) | 904b0ad91838 | `resolve` L16, `source` L65 |
| [server/wakfu_server/combat/combat_groups.py](../../../server/wakfu_server/combat/combat_groups.py) | 20b42e0631d0 | `__init__` L12, `register` L17, `available` L43, `claim` L51, `finish` L63, `release_session` L73, `respawn` L82 |
| [server/wakfu_server/combat/combat_rewards.py](../../../server/wakfu_server/combat/combat_rewards.py) | 13cf931a99a6 | `schema` L24, `load` L50, `award` L81, `wallet` L177, `_xp_info` L197, `report_metadata` L210, `__post_init__` L16 |
| [server/local_game_server.py](../../../server/local_game_server.py) | edbb31c2577a | `known_transports` L99, `position_lease_active` L114, `flush_positions` L128, `flush_position_batches` L144, `pack_text` L210, `realms_local` L215, `fixture` L269, `character_list_local` L282, `player_template` L293, `write_records` L322 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Identificar brecha concreta | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Definir catálogo y estado de instancia | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Autorizar entrada compartida | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Ejecutar oleadas por transición | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Cerrar y repartir una vez | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
