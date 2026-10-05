# Cotejo de código — 30

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**Persistir nivel de oficio no implementa recetas ni mesas. Distinguir spawn del interactivo, carrier de apertura y transacción de fabricación; la mesa portable del merkasaco tampoco demuestra crafting completo.**

Función `level`, línea 20 de [server/wakfu_server/storage/profession_store.py](../../../server/wakfu_server/storage/profession_store.py). SHA-256: `c7cfa49d4888d0d275af4d74e37085833a5cd44b7be67f6e190780b9bc3541b9`.

```python
def level(store, account_id, generation, character_id, profession_id):
    _validate(profession_id)
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        schema(db)
        row = db.execute(
            "SELECT level FROM character_professions WHERE character_id=? AND profession_id=?",
            (character_id, profession_id),
        ).fetchone()
        return 0 if row is None else row["level"]
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/maps/world_static.py](../../../server/wakfu_server/maps/world_static.py) | 40311961155d | `objects` L22, `snapshots` L27, `interaction` L44 |
| [server/wakfu_server/items/haven_bag_furniture.py](../../../server/wakfu_server/items/haven_bag_furniture.py) | 87ccee9fe8fe | `encode_furniture` L11, `decode_furniture` L34, `decode_deploy_request` L62 |
| [server/wakfu_server/storage/profession_store.py](../../../server/wakfu_server/storage/profession_store.py) | c7cfa49d4888 | `schema` L5, `_validate` L15, `level` L20, `ensure_learned` L32, `learned` L67 |
| [server/wakfu_server/items/inventory_items.py](../../../server/wakfu_server/items/inventory_items.py) | e7fefe3fb04f | `schema` L9, `load` L22, `_lease` L38, `grant` L49, `remove` L105, `_varint` L137, `item_proto` L146, `equipment_inventory` L170, `item_form` L191, `insertion` L200 |
| [server/local_game_server.py](../../../server/local_game_server.py) | edbb31c2577a | `known_transports` L99, `position_lease_active` L114, `flush_positions` L128, `flush_position_batches` L144, `pack_text` L210, `realms_local` L215, `fixture` L269, `character_list_local` L282, `player_template` L293, `write_records` L322 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Diagnosticar presencia antes de interacción | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Verificar recursos disponibles | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Decodificar mesa/receta | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Confirmar producción atómica | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Sincronizar productos y progreso | Propuesta; requiere cambio, prueba y revisión del contrato |
| 6. Aceptar mapa y mesa portátil | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
