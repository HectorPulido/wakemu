# 15. No hay grupos de jugadores

Crear parties con invitaciones, miembros y liderazgo coherentes entre sesiones.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**Solucionado totalmente.** Usuario confirma «funciona perfecto grupos» tras las correcciones de disolución y chat de grupo desplegadas en imagen7289b2de, gate430 OK. Aceptación manual del sistema completada.

## Dependencias

13, 14, 29. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Cada personaje pertenece a una sola party; todos sus miembros reciben la misma revisión de roster.

- [Invitación nativa, roster, límite configurado y contratos pendientes](REVISION-RESPUESTAS.md).

## Implementación de codecs — 6 de octubre

**En revision.** Se identificó el recorrido de UI hasta red: salir/expulsar16130→ddS→bxI.kP→1074 y transferir líder18020→ddS→bxI.kQ→1066. Ambos requests llevan groupId/memberId i64; la autorización debe distinguirlos. Invitación1072 incluye tipoPARTY1, nombre con longitud byte e inviterId; respuesta1031 incluye tipo, boolean, dos nombres y contexto i64 (default−1). Salida1049 lleva groupId y IDs hasta agotar el payload, sin count.

`server/wakfu_server/maps/party_wire.py` implementa esos layouts y rechaza longitudes inválidas, UTF8 defectuoso, trailing bytes y tipos/IDs inválidos. Pruebas delegadas; todavía **sin handlers ni mutaciones de membresía**. Snapshot1184 depende de serializar registros fga nativos: no se sustituirá por un blob inventado. Caducidad autoritativa y persistencia de membresía aún pendientes. Artefactos nativos privados: `.runtime/local/review-continuacion-20261004/party-*.javap.txt`.

## Almacenamiento e integración pendiente

Fuente nueva `030_player_parties.sql` y `maps/player_parties.py`: invitaciónUUID con generaciones de ambas sesiones y vencimientoDB; aceptar consume invitación y crea grupo/membresía atómicos; rechazar cancela el ticket exacto. CupoDB por defecto6, máximo nativo6, validado bajo lock de grupo. Solo líder invita/expulsa/transfiere; cualquier miembro puede salir. Si sale el líder, sucede el miembro restante más antiguo; último miembro elimina grupo. Membresía persiste al desconectar; invitaciones exigen sesiones vigentes al aceptar. Son políticas explícitas del emulador, no fórmulas oficiales. Locks por identidades en orden ascendente y PK de personaje impiden pertenencia doble. Gate PostgreSQL delegado, **sin despliegue**.

El ID nativo de party codifica tipo1 en el byte alto. La secuencia SQL inicia en72057594037927937. OE1184 usa blob de líderi64 y registros BinarySerial; probeJava offline confirmó parserPARTY y miembro humano mínimo. Encoder de roster implementado con sección0 de identidad; metadatos adicionales de estado/posición y asociación deben cotejarse antes de emitirlo al cliente. Invitar1156 y los otros codecs pasaron13 pruebas aisladas antes de añadir roster. Faltan dispatcher, vincular respuesta1031 al ticket durable y publicación de roster/deltas. No confundir implementación del servicio con aceptación en juego.

## Gate transaccional inicial

**29 pruebas OK** en Docker con PostgreSQL aislado: layouts nativos, constraints030, cupo concurrente, invitaciones competidoras para un receptor, transferencia/expulsión/sucesión, eliminación de grupo vacío y carrera aceptar/salir. El roster humano mínimo pasa el parser offline, pero la fila visual también necesita HP/nivel/retrato; no emitir todavía el registro mínimo como si fuera integración completa. La clave nativa `cBt` se mantiene como asociación opaca hasta acreditar su productor. Correcciones posteriores de validación estricta de versión e IDs se vuelven a verificar antes de desplegar.

## Roster completo en fuente — 6 de octubre

El codec1184 dejó de limitarse a identidad: ahora incluye secciones nativas1 (combate),2 (muerte),3 (nivel efectivo),5 (vida actual/máxima) y7 (nivel real), con directorio BinarySerial de offsets explícitos. Rechaza HP máximo0, niveles inválidos y estados no booleanos; no emite sección6 de compañeros para personajes humanos. HP máximo ya calculado se envía sin porcentaje adicional para evitar aplicar modificadores dos veces. Gate17 pruebas codec aprobado; cuerpo completo cotejado con lector Java OE/fgn: asociación12, nombreAuditMember, combate=true, muerte=false, nivel efectivo95, HP87/máximo123, nivel real100. Prueba offline del lector, sin publicar una party en el juego.

No desplegado ni conectado al dispatcher. `association_id` sigue siendo entrada explícita pendiente de resolver con evidencia nativa; no se equipara arbitrariamente a account_id. También falta mapear campos restantes de identidad/portrait y actualizaciones de presencia. No se acredita una party visible/funcional por este codec aislado.

Cotejo adicional `bxL/cMv`: `fgj.aXA` se usa como clave de raza/retrato y `aXz` como sufijo de variante. El codec en fuente ahora exige `breed`, `portrait_variant` y `native_identity_flag` explícitos y codifica esos cuatro bytes; no rellena el retrato con ceros. Gate de esta ampliación pendiente. `cBt` se cotejó además con `aTJ.xl()` en la autorización de héroes y registro de oficios (cuenta actual); falta cerrar su mapeo en bootstrap antes de usar account_id en el dispatcher.

El gate ampliado pasó dentro de68 pruebas combinadas; lectorJava OE/fgn confirmó raza8, banderafalse y variante1 junto al resto del roster. El cotejo de bootstrap cerró la asociación: `cmT599 → aTJ.as → eDn/eDo(sección0,primer i64) → aEo → xl`; corresponde a cuenta propietaria. Implementación del dispatcher y actualizaciones de grupo sigue pendiente, sin publicación al juego.

Cotejo y adapter humano:association_id=account_id; variante de retratoint(sex)0/1 respaldada por selectors masculino/femenino; dpL corresponde a héroe y esfalse para personajes normales, independiente de líder. Snapshot durable añadebreed/sex/health_dead. `party_snapshot.packet` exige niveles efectivos explícitos y estado de combate suministrado por caller, valida HP/muerte y produce1184. Gate35 PostgreSQL aislado OK, ambossexos/razas/secciones/rechazos y revisión sin mutación. Dispatcher/publicación/reconexión general pendientes; no se pide prueba manual parcial.

Contrato de respuesta corregido con consumidor nativo:Ow1031 entrega tipoPARTY1, aceptación, nombre del invitador, segundo nombre vacío eID del invitador (noIDparty). FramingNx se retira en bucle del servidor; codec recibebody interno. Parser renombra inviter_id y `player_parties.answer_native` resuelve invitación owned vigente por personaje autenticado/generación/invitador; rechaza segundo nombre/contexto/nombre discordantes y reutiliza revalidación transaccional de membresía/sesiones. Gate39 PostgreSQL aislado OK:flujoOG1072→Ow1031 aceptación/rechazo, spoof/replay/caducidad y sesiones reemplazadas sin mutación.

## Integración completa preparada — 2026-10-06

**En revision.** Dispatcher nativo conectado en fuente:1156→1072→1031→1184; liderazgo1066, expulsión/salida1074 y eliminación1049. El roster se publica solo a miembros, entre mapas, al entrar y cada5s para recuperar publicaciones perdidas y actualizar salud/nivel efectivo/combate. Se lee el checkpoint activo sin modificar combate; si falta, no se inventan valores. Entregas ligadas a la generación capturada; invitaciones fallidas se cancelan por su token. Serialización por grupo con1024 locks acotados, sin sockets bajo el lock de WORLD. Al salir el líder, el miembro más antiguo pasa a liderar por política del emulador. Gate integrado44 pruebas OK en PostgreSQL aislado. Imagen366629bb construida; gate final de imagen y despliegue pendientes.

## Despliegue verificado — 2026-10-06

Imagen `wakemu-player-parties:20261006`, SHA366629bb5a1eaa95fc39a1f605f4541ed04a8060fbf071307ecab5fafb625234. Gate final397 OK en178,76s, sin mounts de fuente/protocolo/migraciones y con PostgreSQL aislado. Compilación AST del servidor en esa imagen OK. World recreado y Docker healthy; listeners15556/15558/18081 disponibles. Migración035 aplicada; maduración900000ms, partycupo6/invitación60s confirmados en DB. Backup privado predespliegue realizado. Falta únicamente aceptación manual de grupos: [prueba completa](PRUEBA-COMPLETA.md). No incluye combate conjunto ni espectadores, que pertenecen a otros issues.

## Regresión detectada en aceptación manual

Usuario confirmó invitación/aceptación, liderazgo y salida, pero al salir de una party de dos quedó el otro personaje en un grupo singleton. Corrección preparada: con menos de dos miembros restantes se elimina la party y se publica1049 con todos los miembros afectados, sin roster1184. Con tres→dos se conserva el grupo y se promueve al más antiguo si sale el líder. Gate44 integrado OK; aún sin desplegar esta corrección.

Aceptación manual2026-10-06:pasos1–5 OK; paso6 expulsa correctamente pero deja singleton, paso7 liderazgo funciona, paso8 panel singleton persiste y chat grupo no funciona. El handler13224 se conecta en fuente como parte de13, pendiente de tests/despliegue. No se afirma aceptación completa de15.

## Correcciones desplegadas — 2026-10-06

Imagen7289b2de589f375e9d0e67faaee590a3e157d9da08cb54a59a28fb4b929147f0, gate430 OK/236,19s en PostgreSQL aislado sin mounts fuente/protocolos/migraciones. Disolución2→0 publica1049 a ambos;3→2 conserva/promueve líder. Chat de grupo13224→606 valida membresía y publica solo a sus miembros, entre mapas. Backup privado pre-party-chat realizado; SQL036 aplicada. Aceptación manual final pendiente.

Postdespliegue:Dockerhealthy,listeners15556/15558/18081 verificados;runtime confirma políticaSQL036 (idiomas6/comunidad4,2048bytes,intervalo200ms).

## Aceptación final — 2026-10-06

El usuario confirma «funciona perfecto grupos» después de la prueba completa de las correcciones: disolución al quedar un solo miembro y chat de grupo incluidos. Issue15 cerrado como **Solucionado totalmente**. Combate conjunto y espectadores conservan sus issues independientes.
