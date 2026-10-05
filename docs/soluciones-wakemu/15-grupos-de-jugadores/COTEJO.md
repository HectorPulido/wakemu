# Cotejo de código — 15

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**La sección social serializada no es por sí sola un servicio de grupos con invitaciones y membresía. Hace falta una autoridad común para chat, combate y reconexión.**

Función `company`, línea 22 de [server/wakfu_server/characters/social.py](../../../server/wakfu_server/characters/social.py). SHA-256: `cf52cfc40899c7bcdc1c286530c01a98b7d13be034820fc4ab520b0ab60b8b2c`.

```python
def company(account_id, character):
    # eSO.qD uses native rank ranges beginning at XP=1. XP=0 falls through
    # to the highest rank and produces negative progress in the client.
    return struct.pack(
        ">qqiqIiB", account_id, character["id"] if character else 0, 0, 0, 0, 1, 0
    )
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/characters/social.py](../../../server/wakfu_server/characters/social.py) | cf52cfc40899 | `company` L22, `adapt` L30 |
| [server/wakfu_server/maps/world.py](../../../server/wakfu_server/maps/world.py) | b41d86cdcc95 | `__init__` L6, `location` L14, `snapshot` L17, `_send` L24, `join` L34, `leave` L46, `update` L57, `broadcast` L69, `emit_location` L80 |
| [server/local_game_server.py](../../../server/local_game_server.py) | edbb31c2577a | `known_transports` L99, `position_lease_active` L114, `flush_positions` L128, `flush_position_batches` L144, `pack_text` L210, `realms_local` L215, `fixture` L269, `character_list_local` L282, `player_template` L293, `write_records` L322 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Definir party separada de NPC | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Validar invitaciones | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Implementar transiciones atómicas | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Sincronizar roster y cambios | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Integrar consumidores | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
