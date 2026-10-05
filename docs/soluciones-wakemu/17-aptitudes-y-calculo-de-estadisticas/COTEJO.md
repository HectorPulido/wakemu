# Cotejo de código — 17

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**La validación y presupuesto de aptitudes ya existen; comprobar selección activa, persistencia y recálculo. El plan debe preservar rechazo antes de mutación y evitar bonus acumulados.**

Función `validate`, línea 24 de [server/wakfu_server/characters/aptitudes.py](../../../server/wakfu_server/characters/aptitudes.py). SHA-256: `53c78f673db63f05f8d8eb232573bb633d3414384def1a019b63ef6a7c155bdf`.

```python
def validate(character, blob):
    if not isinstance(blob, bytes) or len(blob) > 65536:
        raise ValueError("Invalid aptitude sheet")
    allocations = {}
    sheet_level = None
    for tag, value in proto_fields(blob):
        if tag == 24:
            if sheet_level is not None or not isinstance(value, int):
                raise ValueError("Invalid aptitude sheet level")
            signed = (value & 0xFFFFFFFF) - (1 << 32) if value & (1 << 31) else value
            if signed not in (-1, character["level"]):
                raise ValueError("Invalid aptitude sheet level")
            sheet_level = signed
        elif tag == 34 and isinstance(value, bytes):
            fields = list(proto_fields(value))
            data = dict(fields)
            if (
                len(fields) != 2
                or set(data) != {8, 16}
                or any(type(v) is not int for v in data.values())
            ):
                raise ValueError("Invalid aptitude allocation")
            bonus, points = data[8], data[16]
            if (
                bonus not in BONUSES
                or bonus not in BONUS_CATEGORY
                or bonus in allocations
            ):
                raise ValueError("Unknown or duplicate aptitude bonus")
            if not 0 <= points <= 32767:
                raise ValueError("Invalid aptitude points")
            maximum = BONUSES[bonus]["maximum"]
            if maximum and points > maximum:
                raise ValueError("Aptitude bonus exceeds its native maximum")
            allocations[bonus] = points
        else:
            raise ValueError("Invalid aptitude protobuf field")
    if sheet_level is None:
# Fragmento truncado; consultar la función completa en el enlace.
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/characters/aptitudes.py](../../../server/wakfu_server/characters/aptitudes.py) | 53c78f673db6 | `budgets` L14, `validate` L24, `bonuses` L83 |
| [server/wakfu_server/items/builds.py](../../../server/wakfu_server/items/builds.py) | dc8c5378a1c6 | `decode` L11, `signed32` L27, `validate` L31, `response` L65, `response_messages` L89, `rejection_messages` L106, `deck_collection` L151, `equipment_set` L167, `build_set` L183, `equipment_registry` L208 |
| [server/wakfu_server/items/equipment_stats.py](../../../server/wakfu_server/items/equipment_stats.py) | 332fe3101fe5 | `_flat` L21, `bonuses` L48, `effective_character` L133, `combat_resources` L154 |
| [server/wakfu_server/storage/build_journal.py](../../../server/wakfu_server/storage/build_journal.py) | 345f0d271da9 | `_sql` L15, `_checked` L24, `_units` L46, `__init__` L78, `_key` L119, `overlay` L123, `save` L141, `flush` L191, `flush_due` L230, `close` L233 |
| [server/local_game_server.py](../../../server/local_game_server.py) | edbb31c2577a | `known_transports` L99, `position_lease_active` L114, `flush_positions` L128, `flush_position_batches` L144, `pack_text` L210, `realms_local` L215, `fixture` L269, `character_list_local` L282, `player_template` L293, `write_records` L322 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Construir réplica numérica | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Verificar presupuesto y nivel efectivo | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Definir evaluación pura y orden | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Compartir build activa y HP | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Sincronizar resultado autoritativo | Propuesta; requiere cambio, prueba y revisión del contrato |
| 6. Aceptar la reversibilidad | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
