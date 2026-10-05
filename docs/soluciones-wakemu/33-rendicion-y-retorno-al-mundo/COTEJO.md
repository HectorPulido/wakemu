# Cotejo de código — 33

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**El codec admite flags 0 y 1 y retorna bool(flag). El caller de abandono exige verdadero: rechaza el 0 observado. Corregir la máquina de estados del cierre, no aceptar cualquier paquete sin validar identidad.**

Función `continuation`, línea 162 de [server/wakfu_server/combat/combat_results.py](../../../server/wakfu_server/combat/combat_results.py). SHA-256: `7024c0b60b4de6bc2be204825a7e03a99872abc19235c0a171673feacdfba6d8`.

```python
def continuation(fight_id, body):
    """coQ12925: matching fight ID and aUH.huO loss flag (not spectator)."""
    if len(body) != 5:
        raise ValueError("Invalid fight continuation")
    identity, flag = struct.unpack(">iB", body)
    if identity != fight_id or flag not in (0, 1):
        raise ValueError("Foreign fight continuation")
    return bool(flag)
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/combat/combat_abandon.py](../../../server/wakfu_server/combat/combat_abandon.py) | 694de42a2a02 | `_participant` L14, `prepare` L28, `return_to_world` L72 |
| [server/wakfu_server/combat/combat_results.py](../../../server/wakfu_server/combat/combat_results.py) | 7024c0b60b4d | `_number` L10, `_message` L16, `_player` L20, `_monster` L80, `fight_report` L88, `finish_messages` L132, `continuation` L162, `outside_fight_updates` L172 |
| [server/local_game_server.py](../../../server/local_game_server.py) | edbb31c2577a | `known_transports` L99, `position_lease_active` L114, `flush_positions` L128, `flush_position_batches` L144, `pack_text` L210, `realms_local` L215, `fixture` L269, `character_list_local` L282, `player_template` L293, `write_records` L322 |
| [server/wakfu_server/combat/combat_lifecycle.py](../../../server/wakfu_server/combat/combat_lifecycle.py) | 4d79dcf6b5dd | `policy_from_env` L7, `prepare_finish` L24, `outside_progression` L84, `return_to_world` L112 |
| [server/wakfu_server/combat/fight_checkpoint_store.py](../../../server/wakfu_server/combat/fight_checkpoint_store.py) | eb7038e191b7 | `_plain` L11, `snapshot` L28, `__init__` L48, `_session` L59, `save` L68, `read` L118, `end` L135, `recover_interrupted` L158 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Reproducir secuencia observada | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Interpretar flag por ruta | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Diseñar transición terminal idempotente | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Liberar todas las referencias | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Recuperar si falta continuación | Propuesta; requiere cambio, prueba y revisión del contrato |
| 6. Aceptar acción posterior | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
