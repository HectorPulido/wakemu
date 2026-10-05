# Cotejo de código — 27

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**Enviar hora del mundo no implementa clima. La tarea weather está deshabilitada y fuera del registro permitido actual; hacen falta estado climático, reglas y carriers.**

Función `packet`, línea 10 de [server/wakfu_server/maps/world_clock.py](../../../server/wakfu_server/maps/world_clock.py). SHA-256: `ca6a506c2b56e0a5c16398fc3108852322e7af7d64570c73c1268b3e4c026f92`.

```python
def packet(now_ms=None, offset_ms=0):
    if now_ms is None:
        now_ms = time.time_ns() // 1000000
    if type(now_ms) is not int or type(offset_ms) is not int:
        raise ValueError("Clock values must be integer milliseconds")
    return struct.pack(">q", now_ms + offset_ms)
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/cron-service/config.json](../../../server/cron-service/config.json) | b2383fea7f15 | Configuración; revisar valores y uso por el proceso. |
| [server/wakfu_server/storage/global_tasks.py](../../../server/wakfu_server/storage/global_tasks.py) | cb5b91243fff | `__init__` L13, `names` L24, `run` L27 |
| [server/wakfu_server/maps/world_clock.py](../../../server/wakfu_server/maps/world_clock.py) | ca6a506c2b56 | `packet` L10, `daytime` L21 |
| [server/wakfu_server/maps/planting_context.py](../../../server/wakfu_server/maps/planting_context.py) | 707de24e1d5d | `region` L17, `bootstrap` L31, `authorize_family` L77, `encode` L47 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Identificar carriers y reglas | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Modelar zona y tiempo | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Implementar scheduler seguro | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Aplicar a sistemas consumidores | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Publicar y recuperar | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
