# Cotejo de código — 12

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**Decodificar entrada a un combate no implementa invitación/aceptación de duelo. El PvP debe crear dos equipos de jugadores y definir recompensas separadas.**

Función `decode_join`, línea 7 de [server/wakfu_server/combat/combat_multiplayer_wire.py](../../../server/wakfu_server/combat/combat_multiplayer_wire.py). SHA-256: `7013ef1aaed99bfe99939882fb7c5c38813e91be12a697ba9bb32dde9f8149d9`.

```python
def decode_join(body):
    if len(body) != 9:
        raise ValueError("Invalid13241 join request length")
    actor_id, locked = struct.unpack(">qB", body)
    if actor_id == 0 or locked not in (0, 1):
        raise ValueError("Invalid13241 target/autoLock")
    return dict(target_id=actor_id, auto_lock=bool(locked))
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/local_game_server.py](../../../server/local_game_server.py) | edbb31c2577a | `known_transports` L99, `position_lease_active` L114, `flush_positions` L128, `flush_position_batches` L144, `pack_text` L210, `realms_local` L215, `fixture` L269, `character_list_local` L282, `player_template` L293, `write_records` L322 |
| [server/wakfu_server/combat/combat_multiplayer_wire.py](../../../server/wakfu_server/combat/combat_multiplayer_wire.py) | 7013ef1aaed9 | `decode_join` L7, `added` L16, `decode_added` L42, `external` L62, `decode_external` L107, `count` L117 |
| [server/wakfu_server/combat/combat_groups.py](../../../server/wakfu_server/combat/combat_groups.py) | 20b42e0631d0 | `__init__` L12, `register` L17, `available` L43, `claim` L51, `finish` L63, `release_session` L73, `respawn` L82 |
| [server/wakfu_server/combat/combat_phase.py](../../../server/wakfu_server/combat/combat_phase.py) | f77ff7cc4a69 | `action_transition` L9 |
| [server/wakfu_server/combat/combat_results.py](../../../server/wakfu_server/combat/combat_results.py) | 7024c0b60b4d | `_number` L10, `_message` L16, `_player` L20, `_monster` L80, `fight_report` L88, `finish_messages` L132, `continuation` L162, `outside_fight_updates` L172 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Delimitar duelo y agresión | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Crear invitación y reserva | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Construir autoridad compartida | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Procesar acciones por dueño y turno | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Finalizar según política PvP | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
