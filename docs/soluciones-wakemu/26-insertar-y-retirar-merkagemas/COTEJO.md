# Cotejo de código — 26

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**La disposición existente trabaja sobre gemas ya disponibles. Añadir una merkagema requiere consumo desde inventario y autoridad del merkasaco; no basta reordenar habitaciones.**

Función `rearrange_rooms`, línea 276 de [server/wakfu_server/items/haven_bag_store.py](../../../server/wakfu_server/items/haven_bag_store.py). SHA-256: `754b0a142cf077dfed4b81814a00dd8d830017e902b5272810aaa4b3810e0449`.

```python
def rearrange_rooms(config, body):
    """crJ13210: move/swap owned gems between two room slots.

    fvw.nQ(true) selects primary; false selects secondary. Room0's fixed
    primary cannot be removed. Empty targets always receive a primary gem,
    matching fvs.b(BZBZZ). No inventory item can be created by this operation.
    """
    import copy
    import struct

    if len(body) != 4:
        raise ValueError("Invalid haven-bag gem move")
    primary_source, primary_target, source, target = struct.unpack(">BBbb", body)
    if primary_source not in (0, 1) or primary_target not in (0, 1):
        raise ValueError("Invalid haven-bag gem slot")
    if not (0 <= source < 9 and 0 <= target < 9) or source == target:
        raise ValueError("Invalid haven-bag gem room")
    rooms = copy.deepcopy(config["rooms"])
    by_index = {room["index"]: room for room in rooms}
    if source not in by_index:
        raise ValueError("Source room has no owned gem")
    src = by_index[source]
    dst = by_index.get(target)
    if dst is None:
        dst = dict(
            index=target,
            enabled=False,
            primary_ref=-1,
            primary_uid=0,
            secondary_ref=-1,
            secondary_uid=0,
        )
        rooms.append(dst)
    sk = "primary" if primary_source else "secondary"
    dk = "primary" if primary_target else "secondary"

    def gem(room, key):
        return room[key + "_ref"], room[key + "_uid"]
# Fragmento truncado; consultar la función completa en el enlace.
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/items/haven_bag_store.py](../../../server/wakfu_server/items/haven_bag_store.py) | 754b0a142cf0 | `schema` L35, `initial_layout` L56, `load` L70, `save` L134, `rearrange_rooms` L276, `deploy_furniture` L351, `edit_furniture` L384, `gem` L312, `set_gem` L315 |
| [server/wakfu_server/items/haven_bag.py](../../../server/wakfu_server/items/haven_bag.py) | 4bf7c5d1a04c | `own_bag` L9, `leave_result` L69, `validate_leave_request` L75, `entry_result` L82, `map_transition` L92, `entry_messages` L116, `leave_messages` L125, `permission_payload` L184, `decode_permissions` L201, `__init__` L140 |
| [server/wakfu_server/items/haven_bag_furniture.py](../../../server/wakfu_server/items/haven_bag_furniture.py) | 87ccee9fe8fe | `encode_furniture` L11, `decode_furniture` L34, `decode_deploy_request` L62 |
| [server/wakfu_server/items/inventory_items.py](../../../server/wakfu_server/items/inventory_items.py) | e7fefe3fb04f | `schema` L9, `load` L22, `_lease` L38, `grant` L49, `remove` L105, `_varint` L137, `item_proto` L146, `equipment_inventory` L170, `item_form` L191, `insertion` L200 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Separar rearrange de inserción | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Validar permisos y compatibilidad | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Diseñar unidad en layout | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Confirmar entrada/salida atómicamente | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Actualizar mapa y recovery | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
