# Cotejo de código — 2

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**La creación del miembro desde la semilla no implementa una evolución periódica de todos los monstruos ya vivos. Separar germinación de evolución de población.**

Función `monster_growth_member`, línea 282 de [server/wakfu_server/maps/planting_runtime.py](../../../server/wakfu_server/maps/planting_runtime.py). SHA-256: `5247374d25cef0617cb0c93d2ec894572c8c097cdbf5976cd12e552479931c04`.

```python
def monster_growth_member(resource, definition):
    """Explicit local population selection: minimum native level, then reference.

    Prefer family members whose native collection action returns this seed, so
    tutorial creatures without harvesting do not break the farming loop. This
    is a local rule, not the official species distribution or maturity timing.
    """
    from .monsters import REFERENCES, owned_instance
    from .monster_collect import _actions

    seed_refs = {
        s["item_reference"]
        for s in planting.SEEDS.values()
        if s["resource_reference"] == definition["resource_reference"]
    }
    eligible = []
    fallback = []
    for ref, template in REFERENCES.items():
        if template["family_id"] not in definition["monster_family_ids"]:
            continue
        try:
            member = owned_instance(
                ref,
                template["min_level"],
                -1,
                map_id=resource["map_id"],
                x=resource["x"],
                y=resource["y"],
                z=resource["z"],
            )
        except ValueError:
            continue
        key = (template["min_level"], ref)
        fallback.append((key, ref))
        if any(
            raw["csP"] in seed_refs
            and raw["clT"].strip() in ("", 'not IsDead("target")')
            for (m, a), raw in _actions().items()
# Fragmento truncado; consultar la función completa en el enlace.
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/maps/planting_runtime.py](../../../server/wakfu_server/maps/planting_runtime.py) | 5247374d25ce | `state_packet` L260, `growth_schema` L274, `monster_growth_member` L282, `__init__` L16, `begin` L35, `cancel` L102, `complete` L113, `snapshots` L145, `mature` L155, `publish_growth` L216 |
| [server/wakfu_server/maps/monsters.py](../../../server/wakfu_server/maps/monsters.py) | f4bb5a9fbbc1 | `reference` L12, `_java_double_to_int` L18, `statistics` L25, `owned_instance` L43, `native_abilities` L95 |
| [server/wakfu_server/combat/combat_group_store.py](../../../server/wakfu_server/combat/combat_group_store.py) | db0407215064 | `__init__` L15, `_members` L38, `register` L41, `snapshot` L69, `available` L80, `claim` L93, `finish` L116, `release_session` L134, `respawn` L155, `recover_reservations` L170 |
| [server/wakfu_server/combat/combat_group_redis.py](../../../server/wakfu_server/combat/combat_group_redis.py) | 403019de4d6c | `_state` L17, `__init__` L31, `_validate` L78, `_read` L105, `_write` L112, `register` L116, `register_seed` L143, `snapshot` L159, `available` L171, `claim` L181 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Identificar familia y etapas | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Definir el reloj de maduración | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Programar por zona activa | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Aplicar transformación segura | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Sincronizar forma y recuperación | Propuesta; requiere cambio, prueba y revisión del contrato |
| 6. Migrar y aceptar | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.

## Revisión de catálogo y política solicitada

[Familia 68, ausencia de is_boss, ruta de respawn y límites del crecimiento](REVISION-RESPUESTAS.md).
