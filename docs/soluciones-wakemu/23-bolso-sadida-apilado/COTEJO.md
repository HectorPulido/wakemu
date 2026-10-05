# Cotejo de código — 23

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**13713 se construye con identidad y bags(character). El consumidor observado espera una entidad; el error binario puede corromper el modelo visual aunque SQL permanezca íntegro.**

Función `synchronization`, línea 224 de [server/wakfu_server/items/inventory_move.py](../../../server/wakfu_server/items/inventory_move.py). SHA-256: `26517d520a9db01ac30c06f2290082b451c99df7bd7491ee8d1388b8b698c1c4`.

```python
def synchronization(character):
    from .inventory import bags

    return 13713, struct.pack(">q", character["id"]) + bags(character)
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/items/inventory_bags.py](../../../server/wakfu_server/items/inventory_bags.py) | 0b3941c3787b | `remove` L10, `equip` L74 |
| [server/wakfu_server/items/inventory_bag_rules.py](../../../server/wakfu_server/items/inventory_bag_rules.py) | 5f717679b114 | `ordinary` L14 |
| [server/wakfu_server/items/inventory_move.py](../../../server/wakfu_server/items/inventory_move.py) | 26517d520a9d | `decode` L14, `transfer` L41, `synchronization` L224 |
| [server/wakfu_server/items/inventory_uids.py](../../../server/wakfu_server/items/inventory_uids.py) | 2e7c818053c2 | `schema` L5, `allocate` L23, `_reserve` L39, `reserve` L81, `initialize_pool` L85, `replenish` L92 |
| [server/wakfu_server/wire.py](../../../server/wakfu_server/wire.py) | 53c52ffa187c | `minimal_entity` L51, `appearance_section` L102, `initial_progression` L126, `character_levels` L144, `without_equipment_appearance` L156, `varint` L174, `proto_fields` L183, `proto_field` L210, `attribute_sheets` L218, `identity` L249 |
| [server/local_game_server.py](../../../server/local_game_server.py) | edbb31c2577a | `known_transports` L99, `position_lease_active` L114, `flush_positions` L128, `flush_position_batches` L144, `pack_text` L210, `realms_local` L215, `fixture` L269, `character_list_local` L282, `player_template` L293, `write_records` L322 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Preservar el fallo demostrado | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Corregir recuperación antes de aceptar stacks | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Resolver elegibilidad del bolso | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Planificar split transaccional | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Publicar estado válido | Propuesta; requiere cambio, prueba y revisión del contrato |
| 6. Validar conservación y otras rutas | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
