# Chat: cotejo de contratos y routing

## Resultado concreto

El dispatcher de `local_game_server.py` solo atiende 12366 cuando el personaje está cargado. Lo convierte en 674 con `wire.chat`; `World.broadcast` incluye remitente y jugadores del mismo `(map_id,instance_id)`. Un World sintético con cuatro peers entregó solo a dos del mismo mapa/instancia. No se atribuye un radio de proximidad que el código no aplica.

Se ejecutaron ocho solicitudes mediante encoders nativos instalados; siete coinciden con el decoder actual. La octava revela un defecto en gremio:

| Canal | Opcode/clase | Cuerpo nativo | Estado del servidor |
| --- | --- | --- | --- |
| Local | 12366/cmy | u16 bytes UTF8 + texto | Handler presente; salida674 |
| Comercio | 13074/cmx | u16 bytes UTF8 + texto | Decoder presente; sin handler |
| Gremio | 13744/cms | i64 gremio + u16 bytes UTF8 + texto | **Decoder incorrecto**; sin handler |
| Campo de batalla | 13702/cmp | u16 bytes UTF8 + texto | Decoder presente; sin handler |
| Reclutamiento | 13188/cmw | byte idioma + u16 bytes UTF8 + texto | Decoder presente; sin handler |
| Comunidad | 13831/cmr | byte idioma + u16 bytes UTF8 + texto | Decoder presente; sin handler |
| Grupo | 13224/cmt | i64 grupo + u16 bytes UTF8 + texto | Decoder presente; sin handler/party |
| Privado | 13917/cmv | u8 bytes nombre destinatario + nombre + u16 bytes texto + texto | Decoder presente; sin handler |

Las clases nativas `TradeMessageCommand`, `PartyMessageCommand`, `GuildMessageCommand`, `RecruitmentMessageCommand` y `CommunityMessageCommand` acreditan la asociación de canales. Los comandos grupo/gremio además exigen membresía local antes de generar el request; proporcionar un decoder no llena esa membresía.

13744 está agrupado con solicitudes de texto puro en `protocol_codec.decode_body`. Un encoder nativo con gremio456 y texto «Prueba ñ» produce un prefijo i64 que el servidor interpreta como longitud cero: `ValueError: 17 undecoded bytes`. No se afirma que hoy desconecte por este opcode: el dispatcher lo rechaza antes de llamar al decoder. Sí fallaría si se añade handler reutilizando el decoder actual.

## Respuesta y aislamiento

674 es `On`, payload `NQ` sin prefijo de canal. 762 es `NP`: i32 canal seguido del mismo payload. Se probaron ambos con identidad12345 y UTF8. El canal7 fue arbitrario para probar estructura; **no se identifica como privado/grupo/gremio**. Falta cotejar IDs reales y consumidor específico de privados/errores antes de elegir respuesta.

## Solución concreta del servidor

Separar13744 del grupo de texto puro y leer i64 guild_id; validar que coincida con membresía autoritativa. Incorporar handlers separados para los opcodes acreditados. Grupo/gremio consultan sus miembros, privado resuelve nombre contra sesión propia y política de ignorados, y canales públicos consultan alcance/idioma permitido. No usar `World.broadcast` como destino universal: filtra solo ubicación, no membresía ni destinatario.

Conservar identidad del remitente obtenida de la sesión, validar longitud en bytes UTF8 y mantener límites de frecuencia por canal. Cotejar IDs de salida y negativos offline/ignorado/sin grupo; no responder con eco local a un privado rechazado. El máximo/radio y políticas aún necesitan fuente acreditada.

## Límite real

La prueba manual posterior acredita chat local visible y rechazo del privado entre sesiones de auditoría. Grupo/gremio y otros canales siguen sin prueba end-to-end. [Fixtures sintéticos, fallos y hashes](probe-canales-nativos.json).

## Prueba manual con dos clientes

El usuario realizó los envíos solicitados y reportó **ningún mensaje ni error visible**. El log propio registra 13917 a las 22:53:51.851473 UTC y `request_rejected`: **No handler for this opcode in the current session state**. Confirma recepción y rechazo de una petición privada en vivo; falta correlacionar identidad/texto exactos con la captura para distinguirla de un intento previo de Luna. No hubo 12366 ni evento chat en el log inspeccionado, por lo que no se atribuye aún el intento General a un fallo de broadcast.

La ausencia visual de mensaje/error coincide con el rechazo registrado para privado. La solución debe incluir respuesta nativa de error visible además del routing, con destinatario normalizado, sesiones vigentes y eco adecuado al emisor; no basta registrar el rechazo internamente. El intento local necesita verificar canal seleccionado y petición realmente emitida antes de concluir que General llegó al servidor.

[Observación manual y evidencia del servidor](probe-chat-manual-dos-clientes.json). Ambos clientes conectados no acreditan envío del canal local; se mantiene este límite explícito.

## Correlación de captura resuelta

Captura del segundo perfil a las **22:53:51.819789 UTC**: frame 13917 decodificado con destinatario **Audit Builds** y texto **hola**. El servidor registra el mismo opcode unos 32 ms después y lo rechaza por ausencia de handler. Luna confirmó que no envió el mensaje automatizado, por lo que la evidencia corresponde al intento manual del usuario, aunque el texto difiere del sugerido. Queda confirmada la ruta cliente → servidor y su rechazo silencioso; no hay evidencia de entrega al destinatario. En esa captura no se encontró frame 12366; el intento General sigue pendiente de correlación.

## Aviso nativo de rechazo identificado

El consumidor `cis` recibe **349 (`NE`)**, con i16 código seguido de parámetros específicos. Se cotejó su switch: 100 muestra `error.chat.channelNotFound`; 101 lee un nombre mediante `NE.aWL()` y muestra `error.chat.userNotFound`; 102/103 corresponden a no molestar/ignorado y 104 a destinatario propio. **140 muestra `error.chat.generalError` sin parámetro adicional**.

Se ejecutó el parser con cuerpos `0064` y `008c`: ambos devuelven true y códigos100/140. Esto demuestra el layout mínimo, no que la UI haya mostrado esos avisos en vivo. Para una funcionalidad aún no disponible, 349/140 es un candidato nativo comprobado para evitar rechazo silencioso; no enviar 101 a un destinatario realmente conectado ni fingir entrega mediante eco. La ruta implementada debe distinguir destinatario inexistente, reglas de privacidad y error de servicio según sus códigos/argumentos reales.

## Canal local: evidencia negativa delimitada

Se revisaron frames salientes completos de ambos perfiles de auditoría: segundo perfil tiene un 13917, primero ninguno; no se halló 12366 ni los canales comercio/reclutamiento/grupo/comunidad en esa revisión. Esto no demuestra que el broadcast local falle: el envío local no está acreditado. La búsqueda limita su alcance a registros con frame completo y longitud coincidente; no cubre frames partidos si el capturador los emitiera fragmentados.

Se cotejó la ruta nativa `VicinityMessageCommand`: registra canal `aOd.ewS`, normaliza texto con `aNV.iS()` y, si no devuelve null, crea `cmy` y envía la solicitud local. La pestaña visible General por sí sola no demuestra selección de ese canal. Se pidió al usuario un envío explícito en Local para separar el filtro visual de la petición emitida; mientras tanto no se modifican ventanas.

## Canal local confirmado en vivo

El usuario envió **«prueba 123»** y confirmó que General funciona. La captura del segundo cliente registra **12366** a las 23:00:19.107220 UTC; el servidor lo recibe unos 2 ms después, emite **674 (39 bytes) a las dos conexiones** del mismo mapa/instancia y termina sin rechazos en **3,066 ms**. Esta prueba sustituye el pendiente del intento local anterior: no se reproduce un fallo de General en estas condiciones. La recepción visual independiente en ambas ventanas no fue inspeccionada.

El fallo confirmado sigue siendo **privado rechazado sin aviso visible**. Comercio, reclutamiento, comunidad, grupo y gremio mantienen sus hallazgos de código y sus pruebas pendientes; no se extiende el resultado de General a ellos. [Captura correlacionada y resultado](probe-chat-local-manual.json).

## Identificadores nativos y metadatos del emisor

Se ejecutó `aOd.values()` del cliente instalado: Local/VICINITY=1, privado=2, grupo=5, gremio=6, comercio=7, campo de batalla=13; comunidades FR/EN/ES/PT=15/16/17/18 y reclutamiento FR/EN/ES/PT=19/20/21/22. El antiguo fixture NP con 7 representa el identificador de comercio en este enum, no privado. **Falta cotejar que el consumidor NP use directamente ese enum y determinar la respuesta específica del privado**; estos IDs no bastan para dar el routing por implementable.

`wire.chat` escribe bytes fijos `6,4` después del nombre. El parser NQ los interpreta mediante `ML.A` y `UH.pQ`: ejecución nativa devuelve **idiomas [EN, ES] y comunidad ES**. No son flags de permisos. La solución del servidor debe tomar estos metadatos de la cuenta/configuración autoritativa cuando corresponda; el valor fijo actual no acredita soporte correcto de idiomas para otros jugadores. No se reproduce un fallo visual por estos valores.

El primer probe llamó además al formateador `cAn()` y falló porque no había colores de interfaz inicializados; se retiró únicamente esa llamada del harness privado y el enum se ejecutó completo sin GUI. [Resultados y límites](probe-identificadores-canales.json).

## Respuestas específicas: privado y canales

El consumidor **chc** resuelve la duda anterior: **762 no usa IDs aOd directamente**. Lee i32 mediante `eEY.PB`, valida idioma con `bWw.t` y obtiene el canal mediante `aOd.c(eEY)`. Por tanto no codificar 2/5/6/7 en NP suponiendo que son selectores válidos. Los IDs de interfaz documentados arriba conservan su significado, pero no ese layout de salida.

El privado es **720/Oi**: byte de longitud del nombre destinatario, nombre UTF8, i64 ID destinatario y payload **NQ** del emisor. El parser usa byte **con signo** para ese nombre; imponer el límite nativo correspondiente y no copiar ciegamente el máximo255 del otro nombre NQ. Un fixture sintético con destinatario AuditRecipient/67890 y emisor12345/texto Prueba ñ fue aceptado por `Oi.dp`; getters y opcode720 coinciden.

El consumidor compara el ID emisor con `biB.cBt()` para distinguir mensaje propio, elige nombre destinatario o emisor y construye `aOe`; después actualiza conversación y último interlocutor. Esto acredita que el eco requiere identidades correctas. **Falta demostrar si cBt corresponde a cuenta y elegir el flag NQ de forma congruente**; reutilizar sin más `wire.chat` (ID personaje, flagtrue) todavía no queda validado. El paquete debe entregarse únicamente a las dos sesiones autorizadas tras resolver destinatario y privacidad. No se inyectó en las ventanas ni se implementó handler.

Otros handlers de chc están asociados directamente a canales: local674/On→VICINITY; comercio626/Ol→TRADE; grupo606/Og→PARTY; gremio743/NV→GUILD; reclutamiento769/Oj y comunidad655/NR seleccionan por byte idioma. Sus parsers/layouts particulares deben verificarse antes de emitir; NP no sustituye automáticamente estas respuestas. [Probe y límites](probe-respuesta-privada-y-consumidor.json).

## Identidad del eco privado: cuenta comprobada

`biB.cBt()` llama `aTx.cWy().xl()`; aTJ hereda ese getter de eDn, que devuelve el campo aEo. El `toString` nativo de eDn identifica ese primer campo como **AccountInformations.m_account_id**. Queda resuelta la duda anterior: la comparación de mensaje propio en el consumidor720 utiliza **ID de cuenta**, no ID de personaje.

Para que la misma respuesta720 se reconozca como propia en el emisor, su NQ debe llevar ID de **cuenta remitente** y flag de identidad **false** (cuenta); la ruta entrante deja ese flagfalse para el mensaje ajeno. Copiar `wire.chat` actual, que escribe ID personaje/true, falla esa comparación cuando ambos IDs difieren. Los dos personajes de auditoría actuales tienen ID de personaje igual al de cuenta (1/1 y2/2): no serían una prueba suficiente de esta condición. Añadir caso de reproducción con IDs deliberadamente distintos antes de acreditar eco visual.

El consumidor utiliza el ID destinatario Oi.aXD para la conversación del mensaje propio, pero su semántica de cuenta/personaje debe seguirse hasta el modelo de conversación; no se elige por analogía. No se modificó código ni se enviaron respuestas sintéticas a los clientes.

## ID del destinatario: vínculo de personaje

Se siguió `Oi.aXD` hasta `aOe.exD` y `aOf`: en la rama privada construye un vínculo **`characterName_<ID>`** usando ese campo, junto al nombre del interlocutor. El mismo formateador distingue en otras ramas `accountName_<ID>`. Así, el contrato privado mezcla identidades deliberadamente: **NQ ID cuenta del emisor para reconocer el eco; prefijo Oi ID personaje destinatario para el vínculo**. No intercambiar ambos IDs ni asumir que el destinatario es una cuenta por analogía con el emisor.

Solución delimitada: resolver nombre a personaje conectado y su cuenta, construir720 con nombre/ID del personaje destinatario y NQ con cuenta remitente/flagfalse, y entregar a emisor y destinatario únicamente después de validar privacidad. Ensayar cuentas y personajes con IDs distintos, ambos sentidos y vínculos de nombre, antes de dar por validada la integración. El vínculo comprobado es evidencia de bytecode; no se ejecutó el clic ni el eco GUI.
