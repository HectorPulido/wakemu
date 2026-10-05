# Cotejo de código — 6

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**La consulta selecciona stage=1 y el avance vegetal explícito llega a stage=2. No existe en esta función una cadena genérica hasta toda etapa final del catálogo.**

Función `mature`, línea 155 de [server/wakfu_server/maps/planting_runtime.py](../../../server/wakfu_server/maps/planting_runtime.py). SHA-256: `5247374d25cef0617cb0c93d2ec894572c8c097cdbf5976cd12e552479931c04`.

```python
    def mature(self, groups, *, authorize_spawn=lambda resource: True):
        """Local30s growth policy; returns map-scoped broadcasts for main writer.

        SQL outbox survives Redis outages. Caller excludes live players/objects
        and group occupancy before spawn. No lease belongs to a planted world
        resource: it continues growing after its planter logs out.
        """
        due = int((self.store.clock() - self.growth_seconds) * 1000)
        with self.store.connection() as db:
            resources = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM planted_resources WHERE stage=1 AND creation_time<=?",
                    (due,),
                )
            ]
        candidates = []
        for resource in resources:
            definition = planting.RESOURCES[resource["resource_reference"]]
            if definition["monster_resource"] and not authorize_spawn(resource):
                continue
            candidates.append((resource, definition))
        with self.lock, self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            for resource, definition in candidates:
                current = db.execute(
                    "SELECT * FROM planted_resources WHERE resource_uid=?",
                    (resource["resource_uid"],),
                ).fetchone()
                if current is None or dict(current) != resource:
                    continue
                if definition["monster_resource"]:
                    member = monster_growth_member(resource, definition)
                    group_id = -member["id"]
                    group = dict(
                        key=[resource["map_id"], resource["instance_id"], group_id],
                        members=[member],
                    )
# Fragmento truncado; consultar la función completa en el enlace.
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/maps/planting_runtime.py](../../../server/wakfu_server/maps/planting_runtime.py) | 5247374d25ce | `state_packet` L260, `growth_schema` L274, `monster_growth_member` L282, `__init__` L16, `begin` L35, `cancel` L102, `complete` L113, `snapshots` L145, `mature` L155, `publish_growth` L216 |
| [server/wakfu_server/maps/planting.py](../../../server/wakfu_server/maps/planting.py) | 1e7fffafce73 | `decode` L27, `resource_packet` L36, `result_packet` L57, `start_packet` L63, `schema` L73, `prepare` L89, `complete` L142, `publish_groups` L258 |
| [server/wakfu_server/maps/planting_context.py](../../../server/wakfu_server/maps/planting_context.py) | 707de24e1d5d | `region` L17, `bootstrap` L31, `authorize_family` L77, `encode` L47 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Comprobar almacenamiento primero | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Extraer grafo de etapas por referencia | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Persistir próximo cambio y reloj | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Procesar cada transición legal | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Publicar y recuperar | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.

## Comprobación de etapas y acciones

[Scheduler detenido en 2 y tabla nativa de acciones](REVISION-RESPUESTAS.md).
