# Cotejo de código — E09

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**Las lecturas de progreso, merkasaco, inventario y builds preceden al overlay. El hit del journal no evita esta hidratación SQL; mover DDL tampoco elimina por sí solo SELECT redundantes.**

Función `character`, línea 289 de [server/wakfu_server/storage/store.py](../../../server/wakfu_server/storage/store.py). SHA-256: `9e69e69bb17084485601f474ae4a8fb5a262a152c07b604ea03742595b9bb547`.

```python
    def character(self, account_id, character_id, db=None):
        if db is None:
            with self.connection() as connection:
                return self.character(account_id, character_id, connection)
        row = db.execute(
            "SELECT * FROM characters WHERE account_id=? AND id=?",
            (account_id, character_id),
        ).fetchone()
        if row is None:
            raise ValueError("Personaje no encontrado.")
        result = dict(row)
        from wakfu_server.combat_rewards import load as load_progression

        result.update(load_progression(db, result))
        from wakfu_server.haven_bag_store import load

        result["haven_bag"] = load(db, character_id)
        from wakfu_server.inventory import load as load_inventory

        result["inventory_containers"] = load_inventory(db, character_id)
        from wakfu_server.inventory_items import load as load_items

        result["inventory_items"] = load_items(db, character_id)
        result["colors"] = json.loads(result["colors"])
        result["appearance"] = json.loads(result["appearance"])
        result["builds"] = {
            entry["build_index"]: {
                key: entry[key].hex()
                for key in ("sheet", "equipment", "deck", "aptitudes")
            }
            for entry in db.execute(
                "SELECT * FROM character_builds WHERE character_id=?", (character_id,)
            )
        }
        if not result["appearance"]:
            result["appearance"] = dict(
                zip(APPEARANCE_FIELDS[:3], (c - (1 << 24) for c in result["colors"]))
            )
# Fragmento truncado; consultar la función completa en el enlace.
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/storage/store.py](../../../server/wakfu_server/storage/store.py) | 9e69e69bb170 | `__init__` L15, `connection` L78, `password_hash` L90, `register` L95, `authenticate` L113, `digest` L126, `issue_token` L129, `token` L148, `revoke_token` L162, `begin_session` L166 |
| [server/wakfu_server/storage/build_journal.py](../../../server/wakfu_server/storage/build_journal.py) | 345f0d271da9 | `_sql` L15, `_checked` L24, `_units` L46, `__init__` L78, `_key` L119, `overlay` L123, `save` L141, `flush` L191, `flush_due` L230, `close` L233 |
| [server/wakfu_server/storage/profession_store.py](../../../server/wakfu_server/storage/profession_store.py) | c7cfa49d4888 | `schema` L5, `_validate` L15, `level` L20, `ensure_learned` L32, `learned` L67 |
| [server/wakfu_server/items/haven_bag_store.py](../../../server/wakfu_server/items/haven_bag_store.py) | 754b0a142cf0 | `schema` L35, `initial_layout` L56, `load` L70, `save` L134, `rearrange_rooms` L276, `deploy_furniture` L351, `edit_furniture` L384, `gem` L312, `set_gem` L315 |
| [server/wakfu_server/items/inventory_items.py](../../../server/wakfu_server/items/inventory_items.py) | e7fefe3fb04f | `schema` L9, `load` L22, `_lease` L38, `grant` L49, `remove` L105, `_varint` L137, `item_proto` L146, `equipment_inventory` L170, `item_form` L191, `insertion` L200 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Trazar por operación | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Mover schema e inicialización | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Definir snapshot cacheado completo | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Invalidar y coordinar writers | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Comparar costo y corrección | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
