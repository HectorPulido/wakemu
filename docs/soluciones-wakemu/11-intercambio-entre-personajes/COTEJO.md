# Cotejo de código — 11

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**Este movimiento valida inventario propio; no constituye intercambio bilateral. Trade necesita dos propietarios, consentimiento y confirmación atómica, conservando UID y propiedades.**

Función `transfer`, línea 41 de [server/wakfu_server/items/inventory_move.py](../../../server/wakfu_server/items/inventory_move.py). SHA-256: `26517d520a9db01ac30c06f2290082b451c99df7bd7491ee8d1388b8b698c1c4`.

```python
def transfer(store, account_id, generation, character_id, body):
    request = decode(body)
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        _lease(store, db, account_id, generation, character_id)
        from .inventory_uids import schema

        schema(db)
        clone = request["clone_uid"]
        if clone is not None:
            reservation = db.execute(
                "SELECT * FROM inventory_reserved_uids WHERE uid=? AND account_id=? AND generation=? AND character_id=?",
                (clone, account_id, generation, character_id),
            ).fetchone()
            if reservation is None:
                raise ValueError("Partial item UID was not reserved by this session")
            if reservation["used_request"] is not None:
                if bytes(reservation["used_request"]) != body:
                    raise ValueError(
                        "Reserved item UID already consumed by another request"
                    )
                return dict(
                    character=store.character(account_id, character_id, db),
                    packets=[],
                    applied=False,
                )
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=? AND character_id=?",
            (request["uid"], character_id),
        ).fetchone()
        destination = db.execute(
            "SELECT * FROM inventory_containers WHERE uid=? AND character_id=?",
            (request["destination"], character_id),
        ).fetchone()
        source = db.execute(
            "SELECT * FROM inventory_containers WHERE uid=? AND character_id=?",
            (request["source"], character_id),
        ).fetchone()
# Fragmento truncado; consultar la función completa en el enlace.
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/local_game_server.py](../../../server/local_game_server.py) | edbb31c2577a | `known_transports` L99, `position_lease_active` L114, `flush_positions` L128, `flush_position_batches` L144, `pack_text` L210, `realms_local` L215, `fixture` L269, `character_list_local` L282, `player_template` L293, `write_records` L322 |
| [server/wakfu_server/items/inventory_items.py](../../../server/wakfu_server/items/inventory_items.py) | e7fefe3fb04f | `schema` L9, `load` L22, `_lease` L38, `grant` L49, `remove` L105, `_varint` L137, `item_proto` L146, `equipment_inventory` L170, `item_form` L191, `insertion` L200 |
| [server/wakfu_server/items/inventory_move.py](../../../server/wakfu_server/items/inventory_move.py) | 26517d520a9d | `decode` L14, `transfer` L41, `synchronization` L224 |
| [server/wakfu_server/storage/state_journal.py](../../../server/wakfu_server/storage/state_journal.py) | d67f24a195c5 | `__init__` L19, `_call` L24, `field` L31, `encode` L35, `read` L38, `put` L58, `records` L83, `checkpoint` L95 |
| [server/wakfu_server/storage/store.py](../../../server/wakfu_server/storage/store.py) | 9e69e69bb170 | `__init__` L15, `connection` L78, `password_hash` L90, `register` L95, `authenticate` L113, `digest` L126, `issue_token` L129, `token` L148, `revoke_token` L162, `begin_session` L166 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Descubrir protocolo y restricciones | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Crear sesión de intercambio compartida | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Reservar unidades y valores | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Transferir de forma atómica | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Sincronizar y recuperar | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
