# Cotejo de código — E10

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**Itera campos existentes y sustituye equipo cuando encuentra un índice guardado. No añade entradas para nuevos índices ausentes del original. Diferenciar refresh completo, update y registro de creación.**

Función `equipment_set`, línea 167 de [server/wakfu_server/items/builds.py](../../../server/wakfu_server/items/builds.py). SHA-256: `dc8c5378a1c63d0752f70c653394504c8e77340fe1854fa5d79460faa96a27f8`.

```python
def equipment_set(character, original):
    fields = list(proto_fields(original))
    saved = character.get("builds", {})
    out = []
    for tag, value in fields:
        if tag == 10:
            entry = dict(proto_fields(value))
            index = entry.get(8)
            if index in saved and saved[index]["equipment"]:
                value = proto_field(8, index) + proto_field(
                    18, bytes.fromhex(saved[index]["equipment"])
                )
        out.append(proto_field(tag, value))
    return b"".join(out)
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/items/builds.py](../../../server/wakfu_server/items/builds.py) | dc8c5378a1c6 | `decode` L11, `signed32` L27, `validate` L31, `response` L65, `response_messages` L89, `rejection_messages` L106, `deck_collection` L151, `equipment_set` L167, `build_set` L183, `equipment_registry` L208 |
| [server/wakfu_server/wire.py](../../../server/wakfu_server/wire.py) | 53c52ffa187c | `minimal_entity` L51, `appearance_section` L102, `initial_progression` L126, `character_levels` L144, `without_equipment_appearance` L156, `varint` L174, `proto_fields` L183, `proto_field` L210, `attribute_sheets` L218, `identity` L249 |
| [server/local_game_server.py](../../../server/local_game_server.py) | edbb31c2577a | `known_transports` L99, `position_lease_active` L114, `flush_positions` L128, `flush_position_batches` L144, `pack_text` L210, `realms_local` L215, `fixture` L269, `character_list_local` L282, `player_template` L293, `write_records` L322 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Fijar entrada mínima del defecto | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Comprobar merge nativo | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Generar conjunto canónico | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Mantener atomicidad de creación | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Validar UI y replay | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
