# Cotejo de código — 10

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**Ya existe entrega transaccional con recibo. Reutilizar esa barrera al incorporar tablas de drop; no añadir concesións independientes que puedan duplicarse tras reconexión.**

Función `award`, línea 81 de [server/wakfu_server/combat/combat_rewards.py](../../../server/wakfu_server/combat/combat_rewards.py). SHA-256: `13cf931a99a609c558a49577c3e5dd64c7fccfeda02eb81a6efa263946a4eca3`.

```python
def award(store, account_id, generation, character_id, fight, policy=Policy()):
    """Award a winning controlled participant once, under the current lease.

    Returns {character, awarded, xp, kamas}; character contains updated total
    xp/kamas and level. xp/kamas at the top level are this fight's amounts.
    HP maximum must be refreshed by health_store when a level changes.
    """
    if not isinstance(policy, Policy):
        raise ValueError("Explicit local reward Policy required")
    actor = fight.actors.get(character_id)
    if (
        fight.phase != "finished"
        or fight.winner not in (0, 1)
        or actor is None
        or not actor.controlled
        or actor.owner_id != account_id
        or actor.team != fight.winner
    ):
        raise ValueError("Rewards require the own winning fight participant")
    if type(fight.id) is not int or not 0 < fight.id < 2**31:
        raise ValueError("Invalid reward fight identity")
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        schema(db)
        lease = db.execute(
            "SELECT character_id FROM sessions WHERE account_id=? AND generation=? AND expires_at>?",
            (account_id, generation, store.clock()),
        ).fetchone()
        if lease is None or lease["character_id"] != character_id:
            raise ValueError("Session or character lease is stale")
        character = store.character(account_id, character_id, db)
        totals = load(db, character)
        existing = db.execute(
            "SELECT * FROM fight_rewards WHERE generation=? AND fight_id=? AND character_id=?",
            (generation, fight.id, character_id),
        ).fetchone()
        if existing is not None:
            return dict(
# Fragmento truncado; consultar la función completa en el enlace.
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/combat/combat_rewards.py](../../../server/wakfu_server/combat/combat_rewards.py) | 13cf931a99a6 | `schema` L24, `load` L50, `award` L81, `wallet` L177, `_xp_info` L197, `report_metadata` L210, `__post_init__` L16 |
| [server/wakfu_server/combat/combat_results.py](../../../server/wakfu_server/combat/combat_results.py) | 7024c0b60b4d | `_number` L10, `_message` L16, `_player` L20, `_monster` L80, `fight_report` L88, `finish_messages` L132, `continuation` L162, `outside_fight_updates` L172 |
| [server/wakfu_server/items/inventory_items.py](../../../server/wakfu_server/items/inventory_items.py) | e7fefe3fb04f | `schema` L9, `load` L22, `_lease` L38, `grant` L49, `remove` L105, `_varint` L137, `item_proto` L146, `equipment_inventory` L170, `item_form` L191, `insertion` L200 |
| [server/wakfu_server/items/inventory_uids.py](../../../server/wakfu_server/items/inventory_uids.py) | 2e7c818053c2 | `schema` L5, `allocate` L23, `_reserve` L39, `reserve` L81, `initialize_pool` L85, `replenish` L92 |
| [compose.yaml](../../../compose.yaml) | c56c61058637 | Configuración; revisar valores y uso por el proceso. |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Separar kamas de loot | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Definir multiplicadores y RNG | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Validar recompensa e inventario | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Confirmar wallet y objetos juntos | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Emitir resumen y deltas | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
