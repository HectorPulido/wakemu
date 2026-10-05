# Cotejo de código — E04

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**Este decoder maneja guardado 12772 de cuatro blobs, no la petición 13776 de 9 bytes. No usarlo para activar; el rechazo en vivo confirma la falta de esa ruta.**

Función `decode`, línea 11 de [server/wakfu_server/items/builds.py](../../../server/wakfu_server/items/builds.py). SHA-256: `dc8c5378a1c63d0752f70c653394504c8e77340fe1854fa5d79460faa96a27f8`.

```python
def decode(body):
    r = Reader(body)
    character_id = r.number("q")
    blobs = {}
    for key in KEYS:
        size = r.number("I")
        if size > 65536:
            raise ValueError("Build section too large")
        blobs[key] = r.take(size)
    r.finish()
    fields = dict(proto_fields(blobs["sheet"]))
    if 8 not in fields:
        raise ValueError("Missing build index")
    return character_id, fields[8], blobs
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/local_game_server.py](../../../server/local_game_server.py) | edbb31c2577a | `known_transports` L99, `position_lease_active` L114, `flush_positions` L128, `flush_position_batches` L144, `pack_text` L210, `realms_local` L215, `fixture` L269, `character_list_local` L282, `player_template` L293, `write_records` L322 |
| [server/wakfu_server/items/builds.py](../../../server/wakfu_server/items/builds.py) | dc8c5378a1c6 | `decode` L11, `signed32` L27, `validate` L31, `response` L65, `response_messages` L89, `rejection_messages` L106, `deck_collection` L151, `equipment_set` L167, `build_set` L183, `equipment_registry` L208 |
| [server/wakfu_server/storage/store.py](../../../server/wakfu_server/storage/store.py) | 9e69e69bb170 | `__init__` L15, `connection` L78, `password_hash` L90, `register` L95, `authenticate` L113, `digest` L126, `issue_token` L129, `token` L148, `revoke_token` L162, `begin_session` L166 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Fijar la solicitud observada | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Resolver la respuesta pendiente | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Autorizar antes de cambiar | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Confirmar selección y efectos juntos | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Probar respuesta y recuperación | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.

## Revisión posterior a tus respuestas

[Desbloqueo 51, cupo no permanente 24 y respuesta 13811 verificados](REVISION-RESPUESTAS.md). Esta revisión sustituye las dudas anteriores sobre esos contratos. Las referencias a casts son históricas o trabajo de otra sesión; no se continúan aquí.
