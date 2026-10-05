# Cotejo de código — E07

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**response implementa 12284 de guardado. No es respuesta de borrado 12837; falta la operación dedicada, fallback de activa y liberación de controles verificada.**

Función `response`, línea 65 de [server/wakfu_server/items/builds.py](../../../server/wakfu_server/items/builds.py). SHA-256: `dc8c5378a1c63d0752f70c653394504c8e77340fe1854fa5d79460faa96a27f8`.

```python
def response(character, index, status=0):
    # ctU.dp calls eQQ.eP(byte), which indexes values(): OK=0. eQQ.d()
    # returns a separate localization error code (-1 for OK), not the wire byte.
    saved = character.get("builds", {}).get(index)
    has_data = status == 0 and saved is not None
    result = struct.pack(">qibB", character["id"], index, status, int(has_data))
    if has_data:
        from wakfu_server.spells import default_deck

        # Absent protobuf level fields decode as zero. The UI queries its
        # aptitude-level catalog and has no level-zero record; -1 means the
        # current character level, as in the official fresh-character sheets.
        defaults = {
            "sheet": b"",
            "equipment": EMPTY_EQUIPMENT,
            "deck": default_deck(character),
            "aptitudes": EMPTY_APTITUDES,
        }
        for key in KEYS:
            blob = bytes.fromhex(saved[key]) or defaults[key]
            result += struct.pack(">I", len(blob)) + blob
    return result
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/local_game_server.py](../../../server/local_game_server.py) | edbb31c2577a | `known_transports` L99, `position_lease_active` L114, `flush_positions` L128, `flush_position_batches` L144, `pack_text` L210, `realms_local` L215, `fixture` L269, `character_list_local` L282, `player_template` L293, `write_records` L322 |
| [server/wakfu_server/items/builds.py](../../../server/wakfu_server/items/builds.py) | dc8c5378a1c6 | `decode` L11, `signed32` L27, `validate` L31, `response` L65, `response_messages` L89, `rejection_messages` L106, `deck_collection` L151, `equipment_set` L167, `build_set` L183, `equipment_registry` L208 |
| [server/wakfu_server/storage/store.py](../../../server/wakfu_server/storage/store.py) | 9e69e69bb170 | `__init__` L15, `connection` L78, `password_hash` L90, `register` L95, `authenticate` L113, `digest` L126, `issue_token` L129, `token` L148, `revoke_token` L162, `begin_session` L166 |
| [server/wakfu_server/storage/build_journal.py](../../../server/wakfu_server/storage/build_journal.py) | 345f0d271da9 | `_sql` L15, `_checked` L24, `_units` L46, `__init__` L78, `_key` L119, `overlay` L123, `save` L141, `flush` L191, `flush_due` L230, `close` L233 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Capturar delete completo | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Validar índice y referencias | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Confirmar eliminación y selección | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Responder y desbloquear | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Validar lifecycle | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
