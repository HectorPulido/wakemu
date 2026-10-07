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

Sección PET: un byte de presencia de mascota y su `rA` si existe; un byte de presencia de montura y su `rz` si existe. Cotejo posterior de `rz.toString`, `aF` y `aG`: seis i32 BE en orden `definitionId`, `colorRefItemId`, `equippedRefItemId`, `sleepRefItemId`, `health`, `reskinRefItemId`. Se corrige la interpretación anterior: el segundo campo no es XP y el último no es reservado. Sin mascota y con montura son26 bytes. No confundir referencia de item con modelo:18682→76,18704→81,18705→82,18706→83.

Fuente concreta del catálogo: bdata `aMo`, loader `bbp`, conversión `fwn`, registro `fwu`. Exportación offline: 40 modelos; los cuatro dragopavos tienen 20 de vida, gfx 24, 50 XP por nivel y nivel máximo de montura 50. `csW` es XP por nivel, **no nivel mínimo del personaje**. `fvN.aqb` exige vida positiva y no estar en estado de reposo (`gpM`). Prueba con vida 20 permite uso; con 0 lo rechaza.

Velocidad del modelo: `MOUNT_SPEED2`, id 6, 200 ms/celda (+50% frente a NORMAL_RUN_SPEED, 300 ms/celda). Son datos nativos verificados, no estimación. `maps/movement.Movement.validate` solo valida posiciones y extremo de ruta; no hay validación temporal específica de montura. Montarse debe afectar desplazamiento del mundo, sin sumar PM de combate.

## Persistencia y subsistemas ausentes

`inventory_items` guarda UID, propietario, referencia, cantidad, contenedor y slot. `item_proto` emite UID/referencia/cantidad y opciones de elementos; no estado de montura. No hay autoridad persistida para vida, XP, última comida/hambre, reposo, cosmético ni estado montado. El consumidor de item `fvN.d(wS)` sí admite estos campos: no basta con inicializar solo el actor.

Alimentación, curación, pérdida de vida, reposo, nombre y cosméticos requieren sus operaciones nativas y persistencia por UID. Se acreditó el modelo y consumidor de estado; los opcodes y la ejecución completa de esas operaciones siguen sin prueba. El catálogo incluye reglas de comida/pérdida de vida; no copiar valores de una descripción como si toda la mecánica estuviera implementada.

## Carrier caliente y protobuf cotejados posteriormente

`15548` (`cyo`): `i64 character_id + i16 entity_length + entity_blob completo`. El dispatcher `ciu` resuelve actor local u observador y llama `biB.as`; `eGj.as → eHd.ew` parsea el layout completo y notifica cada sección. `bjL`, suscrito a `rw.DM`, actualiza montura/mascota y `canRide`. Esto acredita refrescar PET del actor existente; `12608` no sustituye esa operación porque su consumidor ignora un actor duplicado. Publicar después del commit solo en el mapa/instancia correspondiente.

Descriptor nativo `kX` (`ProtoItem`): campo50 `ProtoPet`. Dentro de este mensaje:1 definitionId int32,2 name string,3 colorItemRefId int32,4 equippedRefItemId int32,5 health int32,6 xp int32,7 lastMealDate int64,8 lastHungryDate int64,9 sleepRefItemId int32,10 sleepdate int64. El estado pertenece al UID, no a una referencia compartida. Top-level58 es `mimiSymbicSkinRefId` int32; su equivalencia exacta con `rz.reskinRefItemId` todavía no está probada.

Integrar en `inventory_items.item_proto` y `wire.minimal_entity`, que actualmente elimina PET mediante `0000`. Resolver slot24 desde `active_build_index`, validar unidad propia no apilada y unir estado por UID. Refrescar con15548 tras equipar/desequipar/activar build, además de emitir PET coherente durante bootstrap. Estos contratos están cotejados; no se atribuye implementación ni prueba GUI de montura a la investigación.

## Estado posterior del servidor y guarda de natación

Las observaciones de ausencia anteriores describen el diagnóstico inicial. La migración010 ya está aplicada en PostgreSQL; 40 modelos y estado por UID se cargan en inventario, ProtoPet y PET de bootstrap. El gate de estado/codec pasó19 pruebas, incluido desmontar durante cooldown sin cambiar `last_mount_at`. Aún faltan handlers y refresh en las transiciones de equipo para habilitar montar completamente.

La condición `beS.bvX()` consulta `VF.k(x,y,z)`, que selecciona la superficie nativa `Vy` y evalúa `bLF & 512`. Se exportó mapa1134 desde `tplg/1134.jar`: 605 chunks, 37.157 superficies y 7.400 celdas de natación; cero discrepancias con `VF.k` después de cargar cada chunk con `VF.g`. Archivo de origen SHA256 `d3211998b492de5fdaf2d3e99f39ffd30af545eed5a8c5df8480ca561e84cb3b`. Herramienta `server/tools/ExportNativeSwimmingMap.java`; catálogo `server/protocol/swimming-maps/1134.json`; lector `wakfu_server.swimming` con3 pruebas de coordenadas, alturas y rechazo de mapas no exportados. Esta guarda todavía no está conectada al dispatcher.

El bit512 acredita natación, no la propiedad `DISABLE_MOUNT=125`, cuya asignación geográfica sigue sin identificar. Mantenerlas separadas: no inventar una equivalencia entre ambas ni considerar otros mapas secos por falta de catálogo. La cobertura de mapas adicional se está exportando antes de integrar la guarda.

## Corrección del significado de dhG/dhH

`beS.dha()` devuelve `bfb`, cuyos `dhG()`/`dhH()` inspeccionan controladores de estado del actor (`hRl:bgi` y `hQY:bfs`) activos; no son propiedades de área geográfica. `bgj/bfg` aplica apariencia nativa de otra referencia (`blk.bG`, `blu`); `bfu` conserva/modifica estado de apariencia/animación. Se debe seguir su autoridad de estados del actor, separada de topología y de `DISABLE_MOUNT`. No construir un catálogo territorial a partir de esos dos booleanos. Probes privados: `mount-bfb-current.txt`, `mount-occupation-types.txt`, `mount-bfg-current.txt`.

## Validación de mapas de natación actualizada

742 mapas cotejados contra VF.k y 219 explícitamente sin catálogo: 192 archivos sin chunks y 27 errores de decoder nativo. No se consideran secos los mapas desconocidos. Gate de swimming: 6 pruebas OK, incluyendo coordenadas/altura, certificados vacíos y rechazo de contadores booleanos. El validador exige enteros estrictos para identidad y contadores. Esta fuente todavía no habilita por sí sola los handlers de montar.

## Cotejo concluyente de propiedades del actor

`rK` decodifica `01 00 01 55 01` como presencia1, contador u16=1 y par propiedad85/valor1. El enum85 es `RELIC_SPECIAL_JUMP`, no125 `DISABLE_MOUNT`. `eHd.fta→eGj.dqu→eGv` escucha `rK.DM`; `eGv.zm` aplica los pares mediante `pGI.b(wU)` y limpia pGI si XP es null. Esto acredita la hidratación del snapshot de propiedades del actor. El servidor actual conserva la propiedad de salto de su plantilla; no emite125 en esa sección. No se elimina85 como parte de monturas: afecta saltar obstáculos.

El incremental12447 mide11 bytes: getLong seguido de3 get. Familia0 corresponde a eHQ; familia1 a ffe. Operaciones PG:1 ADDED,2 REMOVED,3 SUBTRACTED. No confundir el valor del snapshot con la operación incremental. Cotejo javap sobre el cliente instalado, sin modificaciones.
