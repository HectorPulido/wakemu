# Cotejo de código — E05

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**El campo inicial de selección se emite como proto_field(8,0). Guardar blobs no cambia esa autoridad. Hay que enlazar persistencia, serialización y consumidores efectivos.**

Función `build_set`, línea 183 de [server/wakfu_server/items/builds.py](../../../server/wakfu_server/items/builds.py). SHA-256: `dc8c5378a1c63d0752f70c653394504c8e77340fe1854fa5d79460faa96a27f8`.

```python
def build_set(character, original):
    # Native slot zero is permanent, but editable; the fixture additionally
    # contained permanent level20..140 builds, which do not belong to this player.
    list(proto_fields(original))
    saved = character.get("builds", {})
    indices = sorted({0, 1, *saved})
    result = proto_field(8, 0)
    for index in indices:
        if index in saved:
            sheet = bytes.fromhex(saved[index]["sheet"])
        else:
            sheet = b"".join(
                proto_field(tag, value)
                for tag, value in [
                    (8, index),
                    (18, b"Build por defecto" if index == 0 else b"Build 2"),
                    (24, (1 << 64) - 1),
                    (56, 1),
                    (64, int(index == 0)),
                ]
            )
        result += proto_field(18, sheet)
    return result
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/storage/store.py](../../../server/wakfu_server/storage/store.py) | 9e69e69bb170 | `__init__` L15, `connection` L78, `password_hash` L90, `register` L95, `authenticate` L113, `digest` L126, `issue_token` L129, `token` L148, `revoke_token` L162, `begin_session` L166 |
| [server/wakfu_server/storage/build_journal.py](../../../server/wakfu_server/storage/build_journal.py) | 345f0d271da9 | `_sql` L15, `_checked` L24, `_units` L46, `__init__` L78, `_key` L119, `overlay` L123, `save` L141, `flush` L191, `flush_due` L230, `close` L233 |
| [server/wakfu_server/items/builds.py](../../../server/wakfu_server/items/builds.py) | dc8c5378a1c6 | `decode` L11, `signed32` L27, `validate` L31, `response` L65, `response_messages` L89, `rejection_messages` L106, `deck_collection` L151, `equipment_set` L167, `build_set` L183, `equipment_registry` L208 |
| [server/wakfu_server/items/equipment_stats.py](../../../server/wakfu_server/items/equipment_stats.py) | 332fe3101fe5 | `_flat` L21, `bonuses` L48, `effective_character` L133, `combat_resources` L154 |
| [server/wakfu_server/characters/aptitudes.py](../../../server/wakfu_server/characters/aptitudes.py) | 53c78f673db6 | `budgets` L14, `validate` L24, `bonuses` L83 |
| [server/local_game_server.py](../../../server/local_game_server.py) | edbb31c2577a | `known_transports` L99, `position_lease_active` L114, `flush_positions` L128, `flush_position_batches` L144, `pack_text` L210, `realms_local` L215, `fixture` L269, `character_list_local` L282, `player_template` L293, `write_records` L322 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Inventariar todas las lecturas de selección | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Diseñar persistencia compatible | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Unificar el resolver efectivo | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Fijar la revisión de combate | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Validar alternancia y fallback | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
