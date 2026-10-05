# Cotejo de código — 22

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**La selección aleatoria de máscaras elementales ya tiene almacenamiento y serialización. No equivale a identificación interactiva, elección manual, sockets, cargas o sublimaciones; no describir este checkout como si no tuviera propiedades elementales.**

Función `create`, línea 37 de [server/wakfu_server/items/inventory_elements.py](../../../server/wakfu_server/items/inventory_elements.py). SHA-256: `94e29e52159eb06bd41a89bc27ce401e2edeec888d0680039d0c99c13e7fffae`.

```python
def create(reference, *, rng=None):
    from .equipment_stats import CATALOG

    item = CATALOG.get(reference)
    if item is None:
        return None
    selection = dict(damage_elements=0, resistance_elements=0)
    found = False
    for effect in item["effects"]:
        family = effect["generic"]
        if family not in FIELDS:
            continue
        # Native foX.cL uses (int)eVn.So(1), the raw parameter, not level growth.
        count = int(effect["params"][2])
        if not 0 <= count <= len(ELEMENTS):
            raise ValueError("Unsupported native random element count")
        if selection[FIELDS[family]]:
            raise ValueError(
                "Repeated native element selection requires reroll semantics"
            )
        chosen = (SystemRandom() if rng is None else rng).sample(ELEMENTS, count)
        selection[FIELDS[family]] = sum(1 << element for element in chosen)
        found = True
    return selection if found else None
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/items/inventory_elements.py](../../../server/wakfu_server/items/inventory_elements.py) | 94e29e52159e | `schema` L14, `masks` L23, `create` L37, `save` L63, `hydrate` L74, `copy` L94, `bonuses` L104, `proto` L125, `binary_options` L134 |
| [server/wakfu_server/items/inventory_items.py](../../../server/wakfu_server/items/inventory_items.py) | e7fefe3fb04f | `schema` L9, `load` L22, `_lease` L38, `grant` L49, `remove` L105, `_varint` L137, `item_proto` L146, `equipment_inventory` L170, `item_form` L191, `insertion` L200 |
| [server/wakfu_server/items/inventory_actions.py](../../../server/wakfu_server/items/inventory_actions.py) | 9f6e5943d4fc | `destroy` L15, `use_request` L54 |
| [server/wakfu_server/items/inventory_move.py](../../../server/wakfu_server/items/inventory_move.py) | 26517d520a9d | `decode` L14, `transfer` L41, `synchronization` L224 |
| [server/wakfu_server/items/equipment_stats.py](../../../server/wakfu_server/items/equipment_stats.py) | 332fe3101fe5 | `_flat` L21, `bonuses` L48, `effective_character` L133, `combat_resources` L154 |
| [server/wakfu_server/storage/store.py](../../../server/wakfu_server/storage/store.py) | 9e69e69bb170 | `__init__` L15, `connection` L78, `password_hash` L90, `register` L95, `authenticate` L113, `digest` L126, `issue_token` L129, `token` L148, `revoke_token` L162, `begin_session` L166 |
| [docs/protocol/native-equipment-element-selection.md](../../protocol/native-equipment-element-selection.md) | dcb362ac5070 | Configuración; revisar valores y uso por el proceso. |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Separar subfunciones y versiones | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Especificar estado por UID y migration | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Capturar identificación y reasignación | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Implementar efectos de sockets | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Reciclar y sacrificar atómicamente | Propuesta; requiere cambio, prueba y revisión del contrato |
| 6. Añadir/retirar efectos y sublimaciones | Propuesta; requiere cambio, prueba y revisión del contrato |
| 7. Sincronizar todas las representaciones | Propuesta; requiere cambio, prueba y revisión del contrato |
| 8. Recovery y aceptación integral | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.

## Contratos nativos resueltos tras las respuestas

[13787, 12487, 13766 y la condición de engastes sin identificar](REVISION-RESPUESTAS.md).
