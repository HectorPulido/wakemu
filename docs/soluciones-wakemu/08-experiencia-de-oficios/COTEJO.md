# Cotejo de código — 8

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**El almacenamiento de oficios mantiene nivel, no una curva de XP de oficio. La XP del personaje en progression no sustituye ese dominio ni sus mensajes.**

Función `schema`, línea 5 de [server/wakfu_server/storage/profession_store.py](../../../server/wakfu_server/storage/profession_store.py). SHA-256: `c7cfa49d4888d0d275af4d74e37085833a5cd44b7be67f6e190780b9bc3541b9`.

```python
def schema(db):
    db.execute(
        """CREATE TABLE IF NOT EXISTS character_professions(
        character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
        profession_id INTEGER NOT NULL CHECK(profession_id>0),
        level INTEGER NOT NULL CHECK(level BETWEEN 0 AND 200),
        PRIMARY KEY(character_id,profession_id))"""
    )
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/storage/profession_store.py](../../../server/wakfu_server/storage/profession_store.py) | c7cfa49d4888 | `schema` L5, `_validate` L15, `level` L20, `ensure_learned` L32, `learned` L67 |
| [server/wakfu_server/maps/planting.py](../../../server/wakfu_server/maps/planting.py) | 1e7fffafce73 | `decode` L27, `resource_packet` L36, `result_packet` L57, `start_packet` L63, `schema` L73, `prepare` L89, `complete` L142, `publish_groups` L258 |
| [server/wakfu_server/maps/monster_collect.py](../../../server/wakfu_server/maps/monster_collect.py) | 568203257d3b | `_serialized` L14, `decode_request` L28, `decode_result` L49, `_actions` L59, `action` L67, `validate_action` L83, `start_packet` L98, `resolve_target` L111, `schema` L131, `call` L16 |
| [server/wakfu_server/characters/progression.py](../../../server/wakfu_server/characters/progression.py) | 8a560889941a | `level_xp` L14, `character_xp` L20 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Extraer curva y reglas de recompensa | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Diseñar migración coherente | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Conceder una vez por operación | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Sincronizar delta y total | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Validar progreso y recovery | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
