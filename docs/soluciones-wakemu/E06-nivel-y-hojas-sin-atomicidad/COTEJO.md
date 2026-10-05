# Cotejo de código — E06

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**La validación de hojas depende del nivel actual. La subida de nivel y la hidratación deben validar coherencia antes de commits separados; el ensayo fijo 49→50 confirmó persistencia parcial.**

Función `save_build`, línea 383 de [server/wakfu_server/storage/store.py](../../../server/wakfu_server/storage/store.py). SHA-256: `9e69e69bb17084485601f474ae4a8fb5a262a152c07b604ea03742595b9bb547`.

```python
    def save_build(self, account_id, generation, character_id, build_index, blobs):
        if self.build_journal is not None:
            return self.build_journal.save(
                account_id, generation, character_id, build_index, blobs
            )
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            session = db.execute(
                "SELECT character_id FROM sessions WHERE account_id=? AND generation=? AND expires_at>?",
                (account_id, generation, self.clock()),
            ).fetchone()
            if session is None or session["character_id"] != character_id:
                raise ValueError("Sesión o personaje inválidos.")
            character = self.character(account_id, character_id, db)
            from wakfu_server.builds import validate

            validate(character, build_index, blobs)
            previous = character["builds"].get(build_index, {})
            values = [
                blobs[key] or bytes.fromhex(previous.get(key, ""))
                for key in ("sheet", "equipment", "deck", "aptitudes")
            ]
            db.execute(
                "INSERT INTO character_builds VALUES(?,?,?,?,?,?) ON CONFLICT(character_id,build_index) DO UPDATE SET "
                "sheet=excluded.sheet,equipment=excluded.equipment,deck=excluded.deck,aptitudes=excluded.aptitudes",
                (character_id, build_index, *values),
            )
            updated = self.character(account_id, character_id, db)
            from wakfu_server.equipment_stats import effective_character
            from wakfu_server import health_store

            effective = effective_character(updated)
            maximum = effective["max_hp"]
            hp = (
                maximum
                if character["hp"] == character["max_hp"]
                else min(character["hp"], maximum)
            )
# Fragmento truncado; consultar la función completa en el enlace.
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/maps/test_console.py](../../../server/wakfu_server/maps/test_console.py) | 5b51d23e177d | `execute` L17 |
| [server/wakfu_server/characters/aptitudes.py](../../../server/wakfu_server/characters/aptitudes.py) | 53c78f673db6 | `budgets` L14, `validate` L24, `bonuses` L83 |
| [server/wakfu_server/items/builds.py](../../../server/wakfu_server/items/builds.py) | dc8c5378a1c6 | `decode` L11, `signed32` L27, `validate` L31, `response` L65, `response_messages` L89, `rejection_messages` L106, `deck_collection` L151, `equipment_set` L167, `build_set` L183, `equipment_registry` L208 |
| [server/wakfu_server/storage/store.py](../../../server/wakfu_server/storage/store.py) | 9e69e69bb170 | `__init__` L15, `connection` L78, `password_hash` L90, `register` L95, `authenticate` L113, `digest` L126, `issue_token` L129, `token` L148, `revoke_token` L162, `begin_session` L166 |
| [server/wakfu_server/storage/build_journal.py](../../../server/wakfu_server/storage/build_journal.py) | 345f0d271da9 | `_sql` L15, `_checked` L24, `_units` L46, `__init__` L78, `_key` L119, `overlay` L123, `save` L141, `flush` L191, `flush_due` L230, `close` L233 |
| [server/wakfu_server/combat/combat_rewards.py](../../../server/wakfu_server/combat/combat_rewards.py) | 13cf931a99a6 | `schema` L24, `load` L50, `award` L81, `wallet` L177, `_xp_info` L197, `report_metadata` L210, `__post_init__` L16 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Conservar la fixture exacta | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Decidir nivel real versus limitado | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Preparar estado destino antes del commit | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Persistir por una autoridad definida | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Sincronizar después de confirmar | Propuesta; requiere cambio, prueba y revisión del contrato |
| 6. Migrar estados ya parciales | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
