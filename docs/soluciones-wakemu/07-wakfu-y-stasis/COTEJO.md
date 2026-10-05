# Cotejo de código — 7

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**Este commit confirma plantación y consumo; agregar progreso ecológico requiere una regla y un recibo en la misma autoridad. No se puede certificar el cálculo de Wakfu/Stasis por observar crecimiento.**

Función `complete`, línea 142 de [server/wakfu_server/maps/planting.py](../../../server/wakfu_server/maps/planting.py). SHA-256: `1e7fffafce730a1cf34d5ee1f8657c886e5df7283d46a47ba55ca21bd29c85b1`.

```python
def complete(
    store,
    account,
    generation,
    prepared,
    *,
    operation_id,
    stage,
    creation_time,
    result_prefix,
    monster_members=None,
    group_id=None
):
    if not isinstance(operation_id, str) or not 1 <= len(operation_id) <= 128:
        raise ValueError("Invalid planting receipt ID")
    if (
        type(stage) is not int
        or not 0 <= stage <= 127
        or type(creation_time) is not int
        or creation_time < 0
    ):
        raise ValueError("Invalid native resource state")
    character = prepared["character"]
    request = prepared["request"]
    definition = prepared["definition"]
    resource = dict(
        resource_uid=secrets.randbits(62) + 1,
        map_id=character["map_id"],
        instance_id=character["instance_id"],
        x=request["x"],
        y=request["y"],
        z=prepared["z"],
        resource_reference=definition["resource_reference"],
        stage=stage,
        creation_time=creation_time,
    )
    if stage not in definition["stages"]:
        raise ValueError("Resource stage is absent from native definition")
# Fragmento truncado; consultar la función completa en el enlace.
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/maps/planting.py](../../../server/wakfu_server/maps/planting.py) | 1e7fffafce73 | `decode` L27, `resource_packet` L36, `result_packet` L57, `start_packet` L63, `schema` L73, `prepare` L89, `complete` L142, `publish_groups` L258 |
| [server/wakfu_server/maps/monster_collect.py](../../../server/wakfu_server/maps/monster_collect.py) | 568203257d3b | `_serialized` L14, `decode_request` L28, `decode_result` L49, `_actions` L59, `action` L67, `validate_action` L83, `start_packet` L98, `resolve_target` L111, `schema` L131, `call` L16 |
| [server/wakfu_server/maps/planting_context.py](../../../server/wakfu_server/maps/planting_context.py) | 707de24e1d5d | `region` L17, `bootstrap` L31, `authorize_family` L77, `encode` L47 |
| [server/wakfu_server/storage/store.py](../../../server/wakfu_server/storage/store.py) | 9e69e69bb170 | `__init__` L15, `connection` L78, `password_hash` L90, `register` L95, `authenticate` L113, `digest` L126, `issue_token` L129, `token` L148, `revoke_token` L162, `begin_session` L166 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Separar estado personal y población | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Definir política ecológica | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Modelar progreso y recibos | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Aplicar y sincronizar | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Verificar límites y concurrencia | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
