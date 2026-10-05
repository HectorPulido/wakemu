# Cotejo de código — 16

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**Existe un carrier externo, pero espectar requiere snapshot seguido de eventos ordenados y permisos de solo lectura. No otorgar control de actores al reutilizar join.**

Función `external`, línea 62 de [server/wakfu_server/combat/combat_multiplayer_wire.py](../../../server/wakfu_server/combat/combat_multiplayer_wire.py). SHA-256: `7013ef1aaed99bfe99939882fb7c5c38813e91be12a697ba9bb32dde9f8149d9`.

```python
def external(value):
    """cuY13753 exact fields; no guesses about neutral myo/myp/jqi/myu semantics.

    topology is fct/QI, not a participant bootstrap myD of arbitrary shape.
    myr is byte-count q-list; teams is i16-count (q ID,b team); mys b-count(h,h).
    """
    if value["phase_code"] not in range(6):
        raise ValueError("Unknown native external phase")
    lists = (value["myr"], value["teams"], value["mys"])
    if len(lists[0]) > 127 or len(lists[1]) > 32767 or len(lists[2]) > 127:
        raise ValueError("External fight list too long")
    if (
        len(lists[0]) != 2
        or len(set(lists[0])) != 2
        or not set(lists[0]) <= {actor for actor, team in lists[1]}
    ):
        raise ValueError("External fight requires two existing team leaders")
    flags = value["flags"]
    if len(flags) != 4 or any(type(flag) is not bool for flag in flags):
        raise ValueError("Invalid external native flags")
    out = struct.pack(
        ">ibqqhq",
        value["fight_id"],
        value["kind"],
        value["myo"],
        value["myp"],
        value["jqi"],
        value["myu"],
    )
    out += struct.pack(">b", len(lists[0])) + b"".join(
        struct.pack(">q", n) for n in lists[0]
    )
    out += struct.pack(">h", len(lists[1])) + b"".join(
        struct.pack(">qb", *entry) for entry in lists[1]
    )
    out += struct.pack(">b", value["phase_code"]) + bytes(flags)
    out += struct.pack(">b", len(lists[2])) + b"".join(
        struct.pack(">hh", *pair) for pair in lists[2]
# Fragmento truncado; consultar la función completa en el enlace.
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/combat/combat_multiplayer_wire.py](../../../server/wakfu_server/combat/combat_multiplayer_wire.py) | 7013ef1aaed9 | `decode_join` L7, `added` L16, `decode_added` L42, `external` L62, `decode_external` L107, `count` L117 |
| [server/wakfu_server/maps/world.py](../../../server/wakfu_server/maps/world.py) | b41d86cdcc95 | `__init__` L6, `location` L14, `snapshot` L17, `_send` L24, `join` L34, `leave` L46, `update` L57, `broadcast` L69, `emit_location` L80 |
| [server/local_game_server.py](../../../server/local_game_server.py) | edbb31c2577a | `known_transports` L99, `position_lease_active` L114, `flush_positions` L128, `flush_position_batches` L144, `pack_text` L210, `realms_local` L215, `fixture` L269, `character_list_local` L282, `player_template` L293, `write_records` L322 |
| [server/wakfu_server/combat/combat_event_replay.py](../../../server/wakfu_server/combat/combat_event_replay.py) | f72d17c751f9 | `healing_event_source` L295, `validate` L39, `validate` L95, `__init__` L122, `enter` L125, `leave` L136, `__init__` L141, `__call__` L145, `__init__` L385, `__call__` L399 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Separar marcador y espectador | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Publicar ciclo del marcador | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Iniciar snapshot consistente | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Distribuir eventos sin control | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Cerrar y recuperar observación | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
