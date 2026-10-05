# Cotejo de código — 1

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**La finalización contiene transacción, recibo y consumo persistido. El defecto visual no implica ausencia del descuento SQL; falta demostrar el contrato de actualización del inventario en la sesión.**

Función `complete`, línea 142 de [server/wakfu_server/maps/planting.py](../../../server/wakfu_server/maps/planting.py). SHA-256: `1e7fffafce730a1cf34d5ee1f8657c886e5df7283d46a47ba55ca21bd29c85b1`.

```python
def complete(
    store,
    account,
    generation,
    prepared,
    *,
    operation_id,
    stage,
    creation_time,
    result_prefix,
    monster_members=None,
    group_id=None
):
    if not isinstance(operation_id, str) or not 1 <= len(operation_id) <= 128:
        raise ValueError("Invalid planting receipt ID")
    if (
        type(stage) is not int
        or not 0 <= stage <= 127
        or type(creation_time) is not int
        or creation_time < 0
    ):
        raise ValueError("Invalid native resource state")
    character = prepared["character"]
    request = prepared["request"]
    definition = prepared["definition"]
    resource = dict(
        resource_uid=secrets.randbits(62) + 1,
        map_id=character["map_id"],
        instance_id=character["instance_id"],
        x=request["x"],
        y=request["y"],
        z=prepared["z"],
        resource_reference=definition["resource_reference"],
        stage=stage,
        creation_time=creation_time,
    )
    if stage not in definition["stages"]:
        raise ValueError("Resource stage is absent from native definition")
# Fragmento truncado; consultar la función completa en el enlace.
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/maps/planting.py](../../../server/wakfu_server/maps/planting.py) | 1e7fffafce73 | `decode` L27, `resource_packet` L36, `result_packet` L57, `start_packet` L63, `schema` L73, `prepare` L89, `complete` L142, `publish_groups` L258 |
| [server/wakfu_server/maps/planting_runtime.py](../../../server/wakfu_server/maps/planting_runtime.py) | 5247374d25ce | `state_packet` L260, `growth_schema` L274, `monster_growth_member` L282, `__init__` L16, `begin` L35, `cancel` L102, `complete` L113, `snapshots` L145, `mature` L155, `publish_growth` L216 |
| [server/local_game_server.py](../../../server/local_game_server.py) | edbb31c2577a | `known_transports` L99, `position_lease_active` L114, `flush_positions` L128, `flush_position_batches` L144, `pack_text` L210, `realms_local` L215, `fixture` L269, `character_list_local` L282, `player_template` L293, `write_records` L322 |
| [server/wakfu_server/items/inventory_items.py](../../../server/wakfu_server/items/inventory_items.py) | e7fefe3fb04f | `schema` L9, `load` L22, `_lease` L38, `grant` L49, `remove` L105, `_varint` L137, `item_proto` L146, `equipment_inventory` L170, `item_form` L191, `insertion` L200 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Preparar una réplica identificable | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Delimitar consumo y presentación | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Resolver un contrato único de consumo | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Confirmar recurso y semilla juntos | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Publicar después de confirmar | Propuesta; requiere cambio, prueba y revisión del contrato |
| 6. Verificar todas las vistas | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
