# Cotejo de código — E08

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**La guarda exige índice entero entre 0 y 2. El cupo visible de 24 es incoherente con esa frontera; su significado nativo sigue pendiente y no justifica ampliar ciegamente el rango.**

Función `validate`, línea 31 de [server/wakfu_server/items/builds.py](../../../server/wakfu_server/items/builds.py). SHA-256: `dc8c5378a1c63d0752f70c653394504c8e77340fe1854fa5d79460faa96a27f8`.

```python
def validate(character, index, blobs):
    if type(index) is not int or not 0 <= index <= 2:
        raise ValueError("Invalid build index")
    fields = list(proto_fields(blobs["sheet"]))
    data = dict(fields)
    if (
        len(data) != len(fields)
        or set(data) - {8, 18, 24, 56, 64}
        or not {8, 18, 24, 56} <= set(data)
    ):
        raise ValueError("Invalid build sheet")
    if data[8] != index or not isinstance(data[18], bytes) or len(data[18]) > 128:
        raise ValueError("Invalid build identity")
    data[18].decode("utf8")
    if (
        signed32(data[24]) not in (-1, character["level"])
        or not 0 <= data[56] <= 255
        or data.get(64, 0) not in (0, 1)
    ):
        raise ValueError("Invalid build properties")
    if blobs["equipment"]:
        from wakfu_server.equipment import validate_sheet

        validate_sheet(character, blobs["equipment"])
    if blobs["aptitudes"]:
        from wakfu_server.aptitudes import validate as validate_aptitudes

        validate_aptitudes(character, blobs["aptitudes"])
    if blobs["deck"]:
        from wakfu_server.spells import validate_deck

        validate_deck(blobs["deck"], character["breed"], character["level"])
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/items/builds.py](../../../server/wakfu_server/items/builds.py) | dc8c5378a1c6 | `decode` L11, `signed32` L27, `validate` L31, `response` L65, `response_messages` L89, `rejection_messages` L106, `deck_collection` L151, `equipment_set` L167, `build_set` L183, `equipment_registry` L208 |
| [server/wakfu_server/storage/store.py](../../../server/wakfu_server/storage/store.py) | 9e69e69bb170 | `__init__` L15, `connection` L78, `password_hash` L90, `register` L95, `authenticate` L113, `digest` L126, `issue_token` L129, `token` L148, `revoke_token` L162, `begin_session` L166 |
| [server/wakfu_server/storage/build_journal.py](../../../server/wakfu_server/storage/build_journal.py) | 345f0d271da9 | `_sql` L15, `_checked` L24, `_units` L46, `__init__` L78, `_key` L119, `overlay` L123, `save` L141, `flush` L191, `flush_due` L230, `close` L233 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Acotar capacidades nativas | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Definir cupo por personaje | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Actualizar validaciones y schema propuestos | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Preservar referencias y selección | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Probar bordes y recuperación | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.

## Revisión posterior a tus respuestas

[Desbloqueo 51, cupo no permanente 24 y respuesta 13811 verificados](REVISION-RESPUESTAS.md). Esta revisión sustituye las dudas anteriores sobre esos contratos. Las referencias a casts son históricas o trabajo de otra sesión; no se continúan aquí.
