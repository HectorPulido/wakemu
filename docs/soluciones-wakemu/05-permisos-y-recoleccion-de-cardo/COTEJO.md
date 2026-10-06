# Cotejo de código — 5

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**La resolución aquí corresponde a monstruos. No se debe reutilizar sin confirmar el contrato de recolección de plantas, cuya identidad y estado pertenecen a planted_resources.**

La exportación anterior de plantas ya no omite las acciones nativas. [ExportPlantResources.java](../../../sniffer/java/ExportPlantResources.java) recorre `aNl → aNm → aNn[]`; [plant-resources.json](../../../server/protocol/plant-resources.json) conserva los campos y las etapas previos y añade acciones por etapa. Conteo comprobado: 533 referencias únicas, 1.800 etapas y 1.141 acciones con ID único. La procedencia, hashes completos y límites semánticos están en [REVISION-RESPUESTAS.md](REVISION-RESPUESTAS.md).

Los campos de acción probados desde el mapeo de `bbO` son ID, oficio, nivel mínimo, duración, criterio y referencias de producto. Cantidades/probabilidades, XP, transición tras cosechar y el resultado de ocupación vegetal siguen sin quedar acreditados. El handler 12995 también sigue ausente; la exportación solo habilita validación de acción contra recurso y etapa, no concede recompensas.

Función `resolve_target`, línea 111 de [server/wakfu_server/maps/monster_collect.py](../../../server/wakfu_server/maps/monster_collect.py). SHA-256: `568203257d3bff28b133424641d1097e147b1e1f24a577c0c2cdad1de3fd6553`.

```python
def resolve_target(registry, character, monster_id):
    """Resolve only available own NPCs in the actual map and instance."""
    matches = []
    for group in registry.available(character["map_id"], character["instance_id"]):
        for member in group["members"]:
            if member["id"] == monster_id:
                target = dict(
                    member,
                    map_id=group["key"][0],
                    instance_id=group["key"][1],
                    group_key=group["key"],
                )
                if "hp" not in target:
                    target["hp"] = target["stats"]["HP"]
                matches.append(target)
    if len(matches) != 1:
        raise ValueError("Monster harvest target unavailable or ambiguous")
    return matches[0]
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [sniffer/java/ExportPlantResources.java](../../../sniffer/java/ExportPlantResources.java) | 4c1b4b15687e | Exporta recursos, etapas y acciones por etapa desde bdata |
| [server/protocol/plant-resources.json](../../../server/protocol/plant-resources.json) | 2397948397db | 533 recursos, 1.800 etapas, 1.141 acciones; generado desde JAR/bdata local |
| [server/wakfu_server/maps/planting.py](../../../server/wakfu_server/maps/planting.py) | 1e7fffafce73 | `decode` L27, `resource_packet` L36, `result_packet` L57, `start_packet` L63, `schema` L73, `prepare` L89, `complete` L142, `publish_groups` L258 |
| [server/wakfu_server/maps/planting_runtime.py](../../../server/wakfu_server/maps/planting_runtime.py) | 5247374d25ce | `state_packet` L260, `growth_schema` L274, `monster_growth_member` L282, `__init__` L16, `begin` L35, `cancel` L102, `complete` L113, `snapshots` L145, `mature` L155, `publish_growth` L216 |
| [server/wakfu_server/maps/monster_collect.py](../../../server/wakfu_server/maps/monster_collect.py) | 568203257d3b | `_serialized` L14, `decode_request` L28, `decode_result` L49, `_actions` L59, `action` L67, `validate_action` L83, `start_packet` L98, `resolve_target` L111, `schema` L131, `call` L16 |
| [server/local_game_server.py](../../../server/local_game_server.py) | edbb31c2577a | `known_transports` L99, `position_lease_active` L114, `flush_positions` L128, `flush_position_batches` L144, `pack_text` L210, `realms_local` L215, `fixture` L269, `character_list_local` L282, `player_template` L293, `write_records` L322 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Localizar el aviso | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Modelar permisos y ocupación | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Crear la ruta vegetal | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Confirmar cosecha y recompensas | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Emitir estados y errores nativos | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.

## Causa general comprobada

[Fecha enviada como ownerAccount: afecta plantas y árboles](REVISION-RESPUESTAS.md).
