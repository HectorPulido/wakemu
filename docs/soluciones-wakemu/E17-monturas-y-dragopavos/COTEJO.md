# Cotejo de monturas

## Evidencia del personaje y equipamiento

Lectura read-only de `.runtime/local/world.sqlite3`: `Carrier Final`, id 34, nivel 200, posee UID 1099511630525/ref 18682/cantidad 1; el protobuf `character_builds.equipment` de build 0 referencia ese UID en slot 24. No había WAL/SHM junto al archivo; no se certifica la instancia que atendía la captura.

`items/equipment.validate_sheet` permite slot 24 para los dragopavos 18682/18704/18705/18706, exige unidad propia no apilada, nivel efectivo ≥35 y evita duplicados. El catálogo indica sin condición EQUIP para esas referencias. Por tanto, el nivel 0 del tooltip no debe interpretarse como permiso para equipar en nivel 1: el catálogo de equipo exige 35. El estado/progresión de la montura y el nivel del personaje son conceptos distintos.

## Por qué no se habilita montar

`wire.minimal_entity` sustituye `PET` por `0000`. `rw.aG` interpreta esos dos bytes como mascota ausente y montura ausente. El consumidor `bjL.zm` llama `bjo.b(rw)` y `bjo.a(rw)`, y refresca `canRide`. Si falta `rw.Xl`, `bjo.b(rw)` elimina `ikR`, el objeto de montura (`dsT`). `bkO` calcula `canRide` con `cin.as`: sin `dsT`, devuelve falso. Una hoja de equipo con slot 24 no sustituye esa sección.

`cin.as` también comprueba ocupación, propiedad DISABLE_MOUNT, estados del personaje, control del héroe, salud/estado de la montura, natación y animación. En este recorrido no aparece una consulta directa a misión/logro. No hay evidencia para afirmar que la misión sea la causa concreta de la captura; tampoco se acredita aquí todo el sistema de misiones.

`RideMountCommand.e` solo envía `crk` si pasa ese filtro; solicitud 12634, cuerpo vacío. Desmontar usa `crl`, 13928, cuerpo vacío. El dispatcher de `local_game_server.py` no contiene handlers para ninguna. Aunque se habilitara visualmente el botón, la solicitud acabaría en `request_rejected` sin respuesta nativa de montura.

## Contratos nativos acreditados

Respuesta 12634 (`cym`): i64 actor + i32 resultado; 0 OK, 1 MOUNT_DEAD, 2 YOU_ARE_DEAD, 3 MOUNT_DISABLED, 4 FORBIDDEN_LOCATION, 5 OCCUPATION_CANNOT_BE_CANCELLED, 6 RIDING_COOLDOWN, 7 ERROR. `cin` muestra error al actor local; en OK aplica `bjo.gj(true)`. Respuesta 13928 (`cyn`): i64 actor, aplica `gj(false)`.

Sección PET: un byte de presencia de mascota y su `rA` si existe; un byte de presencia de montura y su `rz` si existe. `rz` contiene seis i32: Xp modelo, Xq XP, Xr apariencia por objeto/color, Xs objeto de reposo, Xt salud y Xu reservado/no usado por `bjo.b(rw)` inspeccionado. Sin mascota y con montura son 26 bytes. No confundir referencia de item con modelo: 18682→76, 18704→81, 18705→82, 18706→83.

Fuente concreta del catálogo: bdata `aMo`, loader `bbp`, conversión `fwn`, registro `fwu`. Exportación offline: 40 modelos; los cuatro dragopavos tienen 20 de vida, gfx 24, 50 XP por nivel y nivel máximo de montura 50. `csW` es XP por nivel, **no nivel mínimo del personaje**. `fvN.aqb` exige vida positiva y no estar en estado de reposo (`gpM`). Prueba con vida 20 permite uso; con 0 lo rechaza.

Velocidad del modelo: `MOUNT_SPEED2`, id 6, 200 ms/celda (+50% frente a NORMAL_RUN_SPEED, 300 ms/celda). Son datos nativos verificados, no estimación. `maps/movement.Movement.validate` solo valida posiciones y extremo de ruta; no hay validación temporal específica de montura. Montarse debe afectar desplazamiento del mundo, sin sumar PM de combate.

## Persistencia y subsistemas ausentes

`inventory_items` guarda UID, propietario, referencia, cantidad, contenedor y slot. `item_proto` emite UID/referencia/cantidad y opciones de elementos; no estado de montura. No hay autoridad persistida para vida, XP, última comida/hambre, reposo, cosmético ni estado montado. El consumidor de item `fvN.d(wS)` sí admite estos campos: no basta con inicializar solo el actor.

Alimentación, curación, pérdida de vida, reposo, nombre y cosméticos requieren sus operaciones nativas y persistencia por UID. Se acreditó el modelo y consumidor de estado; los opcodes y la ejecución completa de esas operaciones siguen sin prueba. El catálogo incluye reglas de comida/pérdida de vida; no copiar valores de una descripción como si toda la mecánica estuviera implementada.
