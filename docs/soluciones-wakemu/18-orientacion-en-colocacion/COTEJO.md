# Cotejo de código — 18

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**Exige fase active y turno sincronizado; rechaza placement. Para orientación en colocación hace falta una transición distinta con validación de actor y carrier comprobado.**

Función `apply`, línea 40 de [server/wakfu_server/combat/combat_orientation.py](../../../server/wakfu_server/combat/combat_orientation.py). SHA-256: `e8fea1e821067d33b8995a55f9fdab2e8b6f1654c9f4f83bea02cf489ccbee85`.

```python
def apply(runtime, owner_id, body):
    identity, direction = decode_request(body)
    fight = runtime.fight
    if fight.phase != "active" or runtime.awaiting_ack is not None:
        raise ValueError("Orientation requires an active synchronized turn")
    actor = fight._current_owned(owner_id, identity)
    next_action = runtime.action_id + 1
    packet = response(fight.id, next_action, identity, direction)
    # Everything validates before changing actor facing or action counters.
    runtime.action_id = next_action
    actor.direction = direction
    event = fight._event(
        "orientation", actor_id=identity, direction=direction, cost_ap=0, cost_mp=0
    )
    return dict(packets=[packet, runtime._flush()], event=event, direction=direction)
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/combat/combat_orientation.py](../../../server/wakfu_server/combat/combat_orientation.py) | e8fea1e82106 | `decode_request` L11, `response` L20, `apply` L40 |
| [server/local_game_server.py](../../../server/local_game_server.py) | edbb31c2577a | `known_transports` L99, `position_lease_active` L114, `flush_positions` L128, `flush_position_batches` L144, `pack_text` L210, `realms_local` L215, `fixture` L269, `character_list_local` L282, `player_template` L293, `write_records` L322 |
| [server/wakfu_server/combat/combat_phase.py](../../../server/wakfu_server/combat/combat_phase.py) | f77ff7cc4a69 | `action_transition` L9 |
| [server/wakfu_server/combat/combat_bootstrap.py](../../../server/wakfu_server/combat/combat_bootstrap.py) | ff43dba3aa3a | `placement_positions` L12, `placement_messages` L23, `player_payload` L109, `create_placement` L134, `target_position` L243 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Capturar solicitud en colocación | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Separar autorización por fase | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Definir respuesta nativa de colocación | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Persistir facing en encuentro | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Probar frontera de inicio | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
