# Cotejo de código — 0

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**Carga tablas SQL antes de llamar a build_journal.overlay. La propuesta Redis primero exige cambiar la ruta de lectura; aumentar el intervalo de flush no basta.**

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
| [server/local_game_server.py](../../../server/local_game_server.py) | edbb31c2577a | `known_transports` L99, `position_lease_active` L114, `flush_positions` L128, `flush_position_batches` L144, `pack_text` L210, `realms_local` L215, `fixture` L269, `character_list_local` L282, `player_template` L293, `write_records` L322 |
| [server/wakfu_server/maps/monster_wander.py](../../../server/wakfu_server/maps/monster_wander.py) | 4bfdd278846d | `point` L13, `movement_packet` L17, `plan` L30, `wander_location` L68 |
| [server/wakfu_server/combat/combat_spell_transaction.py](../../../server/wakfu_server/combat/combat_spell_transaction.py) | debfa4a3a487 | `prepare_spell_transaction` L27 |
| [server/wakfu_server/combat/combat_spell_commit.py](../../../server/wakfu_server/combat/combat_spell_commit.py) | ed6d96b02eea | `commit_spell_transaction` L13, `stage` L16 |
| [server/wakfu_server/storage/store.py](../../../server/wakfu_server/storage/store.py) | 9e69e69bb170 | `__init__` L15, `connection` L78, `password_hash` L90, `register` L95, `authenticate` L113, `digest` L126, `issue_token` L129, `token` L148, `revoke_token` L162, `begin_session` L166 |
| [server/wakfu_server/storage/build_journal.py](../../../server/wakfu_server/storage/build_journal.py) | 345f0d271da9 | `_sql` L15, `_checked` L24, `_units` L46, `__init__` L78, `_key` L119, `overlay` L123, `save` L141, `flush` L191, `flush_due` L230, `close` L233 |
| [server/wakfu_server/storage/state_journal.py](../../../server/wakfu_server/storage/state_journal.py) | d67f24a195c5 | `__init__` L19, `_call` L24, `field` L31, `encode` L35, `read` L38, `put` L58, `records` L83, `checkpoint` L95 |
| [server/cron-service/config.json](../../../server/cron-service/config.json) | b2383fea7f15 | Configuración; revisar valores y uso por el proceso. |
| [compose.yaml](../../../compose.yaml) | c56c61058637 | Configuración; revisar valores y uso por el proceso. |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Medir la latencia completa | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Reducir coste por grupo | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Separar geometría de transacciones | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Diseñar lectura Redis primero por dominio | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Persistir con garantías antes del ACK | Propuesta; requiere cambio, prueba y revisión del contrato |
| 6. Implementar flush de 1.200 segundos | Propuesta; requiere cambio, prueba y revisión del contrato |
| 7. Aislar persistencia y sockets lentos | Propuesta; requiere cambio, prueba y revisión del contrato |
| 8. Aceptar por carga y corrección | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.

## Evidencia adicional ejecutada

[Cotejo posterior a las respuestas del usuario](REVISION-RESPUESTAS.md).
