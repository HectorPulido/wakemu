# Cotejo de código — 3

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**El registro permitido contiene flush de posiciones, builds y grupos; population no está entre las tareas admitidas. Activar solamente su configuración no implementa reproducción.**

Función `run`, línea 27 de [server/wakfu_server/storage/global_tasks.py](../../../server/wakfu_server/storage/global_tasks.py). SHA-256: `cb5b91243fff63ea0b35581b7edc52b42ccf7b57846c1c8071c71bfbb87ed2f1`.

```python
    def run(self, name, request_id):
        if name not in self.callbacks:
            raise ValueError("Unknown global task")
        if not isinstance(request_id, str) or not request_id or len(request_id) > 200:
            raise ValueError("Global task requires a bounded occurrence ID")
        if not request_id.startswith(name + ":"):
            raise ValueError("Occurrence does not belong to task")
        with self.lock:
            now = self.clock()
            self.completed = {k: v for k, v in self.completed.items() if v[0] > now}
            key = (name, request_id)
            if key in self.completed:
                return dict(self.completed[key][1], deduplicated=True)
            self.callbacks[name]()
            result = dict(task=name, request_id=request_id, status="completed")
            self.completed[key] = (now + self.retention_seconds, result)
            return dict(result, deduplicated=False)
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/maps/planting_runtime.py](../../../server/wakfu_server/maps/planting_runtime.py) | 5247374d25ce | `state_packet` L260, `growth_schema` L274, `monster_growth_member` L282, `__init__` L16, `begin` L35, `cancel` L102, `complete` L113, `snapshots` L145, `mature` L155, `publish_growth` L216 |
| [server/wakfu_server/combat/combat_groups.py](../../../server/wakfu_server/combat/combat_groups.py) | 20b42e0631d0 | `__init__` L12, `register` L17, `available` L43, `claim` L51, `finish` L63, `release_session` L73, `respawn` L82 |
| [server/wakfu_server/combat/combat_group_store.py](../../../server/wakfu_server/combat/combat_group_store.py) | db0407215064 | `__init__` L15, `_members` L38, `register` L41, `snapshot` L69, `available` L80, `claim` L93, `finish` L116, `release_session` L134, `respawn` L155, `recover_reservations` L170 |
| [server/cron-service/config.json](../../../server/cron-service/config.json) | b2383fea7f15 | Configuración; revisar valores y uso por el proceso. |
| [server/wakfu_server/storage/global_tasks.py](../../../server/wakfu_server/storage/global_tasks.py) | cb5b91243fff | `__init__` L13, `names` L24, `run` L27 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Inventariar vías actuales de creación | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Definir reglas de apareamiento | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Persistir población y eventos de nacimiento | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Evaluar solo zonas con jugadores | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Confirmar y publicar nacimiento | Propuesta; requiere cambio, prueba y revisión del contrato |
| 6. Desactivar regeneración incompatible | Propuesta; requiere cambio, prueba y revisión del contrato |
| 7. Controlar capacidad y recuperación | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.

## Revisión de catálogo y política solicitada

[Familia 68, ausencia de is_boss, ruta de respawn y límites del crecimiento](REVISION-RESPUESTAS.md).
