# Diagnóstico — 29

## Contexto registrado

**Confirmado parcialmente:** `maps/world_static.py::interaction` clasifica puertas/teleporters, pero no ejecuta lógica de mazmorra. La ruta `12870` revisada registra numerosas interacciones y continúa sin resolverlas. `wire.py` vacía progreso heredado de mazmorra; eso no implementa instancias ni salas.

**Posible solución:** accesos, instancia compartida para el grupo, salas/encuentros, progreso, condiciones y salida. **Validación:** entrada con requisitos válidos, dos jugadores en la misma instancia, victoria y abandono sin quedar atrapados.

## Lectura actual

La ruta actual rechaza instancias distintas de 0 y solo soporta determinados transportes. Mazmorras requieren sesiones de instancia, acceso, progresión y recuperación; permitir puertas no completa el sistema.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Primer bloqueo funcional verificado — 2026-10-07

El componente de sesión ya existe en `server/wakfu_server/maps/dungeon_instances.py` con esquema en `server/migrations/065_dungeon_instances.sql`. Aún falta un caller que cree o recupere la sesión desde el acceso normal candidato a Jalató y mueva la party. El catálogo `server/protocol/native-generic-teleporters.json` identifica el objeto 26842 del mapa 527 y la opción 2504 hacia el mapa 1086; esa opción lleva el criterio `not IsNeoServer()` y `cyZ=91`. La lectura de plantillas enlaza 91 con definición 90. La opción Neo es distinta (4759/1459/199/207) y no debe mezclarse con la ruta normal.

`server/wakfu_server/maps/generic_transports.py::resolve` verifica origen y proximidad autoritativa, pero rechaza cualquier criterio no vacío y `cyZ >= 0`; el rechazo está probado en `server/tests/test_generic_transports.py::test_native_condition_is_never_silently_waived`. `local_game_server.py` enruta el uso 12296 a ese resolver y el 12870 solo clasifica/loguea una interacción `teleporter`; todavía no llama al nuevo servicio ni cambia posición. El campo 91 es una plantilla; el servicio asigna un `instance_id` generado aparte. El callback de autorización es obligatorio y debe resolver el criterio/proximidad nativos; no hay implementación acreditada de ese callback.

El servicio `maps/dungeon_transport.py` resuelve solo la ruta normal configurada de 12296 y requiere callbacks explícitos de criterio y proximidad. `maps/dungeon_instances.py` valida el roster bajo locks, crea/reutiliza run y miembros, y cambia las ubicaciones de todos los personajes dentro de la misma transacción; la prueba cubre rollback y requests concurrentes.

La configuración nativa exportada de eEL identifica el campo global IS_NEO_SERVER, clave `server.group.isneo`, con valor predeterminado `false`. La migración 068 agrega el ajuste explícito dungeon_server_mode.is_neo_server=false y maps/dungeon_criteria.py evalúa solo `IsNeoServer()` y `not IsNeoServer()`, rechazando otras expresiones o datos malformados. El parser nativo registra IsNeoServer como IS_NEO_SERVER (tipo 325). No se halló el visitor que implementa el significado de ese nodo; que lea la clave server.group.isneo es una inferencia fuerte del nombre y alcance de configuración, no una llamada de código cotejada. Esto permite configurar el modo sin abrir transportes automáticamente. Todavía no hay integración dispatcher ni comprobación de proximidad en el caller.

Para configurar el modo local, el operador cambia `settings.name='dungeon_server_mode'` y conserva `version=1` junto con un booleano `is_neo_server`; el helper valida el valor cada vez que evalúa el criterio. La migración no resuelve ni perdona requisitos adicionales de acceso.

El catálogo aKU conserva cno() como referencias de monstruos de una definición de mazmorra y el consumidor las usa para búsqueda por nombre. Ese camino no expone índice de sala, conteo, nivel ni coordenadas de aparición. `combat-maps/1086.json.gz` declara que contiene superficies estáticas y excluye actores dinámicos; `native-generic-teleporters.json` sí da los sectores y enlaces 26845/26850/26849/26853, pero no su población. Por tanto, la composición exacta de encuentros del mapa 1086 sigue sin fuente acreditada en el conjunto exportado; las salas y reglas de derrota/reintento siguen bloqueando un ciclo jugable.

## Qué falta para confirmar el recorrido

- Mazmorra priorizada, mapas/puertas, geometría, llaves y progresión.
- Dificultad/XP/loot, rejoin, lockouts y reset de instancia.
- Protocolo de UI mazmorra, stasis y fin, no solo teleport.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
