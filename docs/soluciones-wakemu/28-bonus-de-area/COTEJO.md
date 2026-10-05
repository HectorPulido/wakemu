# Cotejo de código — 28

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**La región aporta contexto geográfico, pero no implementa un cálculo de bonus de área. Identidad de zona, condiciones ecológicas y composición de modificadores deben compartir versión.**

Función `region`, línea 17 de [server/wakfu_server/maps/planting_context.py](../../../server/wakfu_server/maps/planting_context.py). SHA-256: `707de24e1d5d4f3477f7d749ae777dd748657da69a12e77934d338859779772c`.

```python
def region(map_id, region_id):
    match = next(
        (
            r
            for r in MAPS.get(map_id, {}).get("regions", [])
            if r["region_id"] == region_id
        ),
        None,
    )
    if match is None:
        raise ValueError("Unknown native map region")
    return match
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/maps/planting_context.py](../../../server/wakfu_server/maps/planting_context.py) | 707de24e1d5d | `region` L17, `bootstrap` L31, `authorize_family` L77, `encode` L47 |
| [server/wakfu_server/items/equipment_stats.py](../../../server/wakfu_server/items/equipment_stats.py) | 332fe3101fe5 | `_flat` L21, `bonuses` L48, `effective_character` L133, `combat_resources` L154 |
| [server/wakfu_server/maps/world.py](../../../server/wakfu_server/maps/world.py) | b41d86cdcc95 | `__init__` L6, `location` L14, `snapshot` L17, `_send` L24, `join` L34, `leave` L46, `update` L57, `broadcast` L69, `emit_location` L80 |
| [server/cron-service/config.json](../../../server/cron-service/config.json) | b2383fea7f15 | Configuración; revisar valores y uso por el proceso. |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Inventariar origen de cada bonus | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Modelar condiciones por revisión | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Introducir modificadores nombrados | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Sincronizar cambios de zona/condición | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Validar matemática y lifecycle | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
