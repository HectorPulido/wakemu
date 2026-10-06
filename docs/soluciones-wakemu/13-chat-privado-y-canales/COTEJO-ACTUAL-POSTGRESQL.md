# Privados: cotejo actual del servidor

`13917` tiene decoder en `protocol_codec.py` pero carece de handler en `local_game_server.py`; cae en request_rejected. General12366 usa674 y broadcast. Esta es una brecha de implementación, no una ausencia de datos por investigar.

## Contratos cotejados

Request13917: longitud u8 y nombre UTF-8 del destinatario; longitud u16 y textoUTF-8. Restringir nombre a1–127 bytes por encoder nativo de byte con signo y rechazar tails/payloads truncados.

Respuesta720/Oi: nombre del destinatario con longitud u8, ID i64 de personaje destinatario, seguido del NQ: nombre de emisor con longitud u8 (hasta255 bytes, distinto del prefijo del destinatario), máscara de idioma byte, comunidad byte, ID i64 de **cuenta** emisora, identidad=false, longitud u16 y texto UTF-8. El consumidor distingue el echo propio por cuenta; no reutilizar wire.chat, que usa personaje/identity=true.

Error349/NE: i16 code. Usuario offline/inexistente101 añade nombre con longitud **u16**; self104 y error general140 tienen contrato cotejado.102/103 corresponden a DND/ignore, pero su autoridad no existe aún: no afirmar implementación de estas preferencias.

## Ruta de backend actual

El dispatcher de `local_game_server.py` ya decodifica13917 y delega a `WORLD.private_chat`. La resolución usa `casefold`, solo sobre jugadores cargados, y permite mapas distintos. Bajo `World.lock` verifica la generación y la cuenta del emisor, y un callback PostgreSQL consulta `current_character_session` para ambos lados: cuenta, generación, personaje seleccionado y TTL vigentes. El peer del destinatario procede del registro actual de `World.players`. Sólo se envía720 a destinatario y emisor; los rechazos no generan eco. Offline/no seleccionado responde101, self104, y un error de envío informa140 cuando todavía se puede escribir al emisor.

La función escribe primero en el socket destinatario y después en el del emisor. Si falla el segundo envío, el destinatario puede haber recibido ya el mensaje; no existe atomicidad entre sockets ni promesa de entrega exactamente una vez. En la revisión validada por el gate93, la consulta PostgreSQL de lease sucedía dentro de `World.lock`; ese bloqueo no serializaba `begin_session`. La ampliación posterior en fuente captura peers bajo el lock, valida PostgreSQL fuera y revalida generación/conexión antes de enviar también fuera del lock. Esta ampliación está pendiente de regresión; conserva la carrera posible entre validación y desconexión, sin redirigir el mensaje a un peer sustituto. También se mantienen las preferencias DND/ignore102/103 sin implementar. El handler limita además el texto a512 caracteres y 200ms entre solicitudes, aunque el encoder de respuesta admite hasta2048 bytes.

## Revalidación PostgreSQL / protocolo — 2026-10-05

Dentro de un contenedor efímero `world`, con el código del checkout montado read-only, corrió `test_world test_wire test_protocol_codec test_chat_console test_api_authorization test_postgres_store_auth`: **93 tests OK**. Los esquemas PostgreSQL son aislados mediante `PostgresCase` y migraciones001–008.

Las regresiones de `test_world` cubren mapas distintos, nombres casefold, tercero sin entrega, IDs de cuenta/personaje distintos, discrepancia cuenta/personaje rechazada, offline101, self104, emisor obsoleto, destinatario con lease stale, reemplazo del peer, error OSError en socket receptor y en eco emisor. `test_postgres_store_auth.test_current_character_session_tracks_selection_clear_replacement_and_expiry` comprueba selección, clear, cambio a otro personaje, reemplazo de sesión y expiración TTL. `test_wire` cubre el cuerpo720, texto UTF-8 2048 bytes, destinatario firmado máximo127, nombre NQ emisor unsigned hasta255 y errores101(u16 nombre), 104/140(i16 código); códigos e identidades inválidos se rechazan.

La evidencia nativa existente acepta la respuesta sintética con `Oi.dp`, y su parser `NQ` lee la longitud de nombre emisor como byte unsigned. No se repitió JVM en esta ejecución: el contenedor `world` no contiene Java. No se probó GUI ni comunicación live de dos clientes; DND/ignore siguen fuera de alcance, por lo que E13 no se declara cerrado.

Fuentes: [revisión nativa](REVISION-RESPUESTAS.md), dumps privados de chat y fixture PrivateChatResponseProbe. El encoder y la ruta dirigida de backend ya están presentes; esta validación no certifica UI/entrega en vivo ni preferencias de privacidad.

## Gate histórico del encoder, anterior al router

En el gate inicial se añadieron `wire.private_chat` y `wire.private_chat_error`, antes de conectar request13917 al router/dispatcher. En contenedor Docker, `test_wire test_protocol_codec`: **30 tests OK**.

Las regresiones fijan identidades deliberadamente distintas (NQ lleva ID de cuenta emisora y flagfalse; vínculo Oi lleva ID de personaje destinatario), nombre destinatario UTF-8 de127 bytes y texto de2048 bytes. Error101 se codifica como i16 seguido de longitud de nombre u16; Oi conserva su longitud de destinatario u8. Se verifican códigos101/104/140 y rechazo de códigos no soportados.

El análisis Java existente aceptó un payload sintético mediante `Oi.dp`; el bytecode de `NQ` lee longitud del nombre emisor como byte unsigned (`& 255`), mientras el parser Oi mantiene el límite firmado127 del destinatario. La primera regresión detectó que el encoder aplicaba127 al nombre emisor también; root corrigió el límite a255 y el gate pasó. La imagen `world` no incluye JVM, por lo que esta vuelta no repitió el probe Java. Ese gate inicial no acreditaba entrega. El router/dispatcher se incorporó después y pasó el gate93 descrito arriba; la entrega gráfica sigue pendiente.
