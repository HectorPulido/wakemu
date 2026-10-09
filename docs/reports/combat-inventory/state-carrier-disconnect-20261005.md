# Desconexión del perfil state-carrier-test

Incidente separado del cuervo. Investigación de solo lectura; sin GUI, cambios de motor ni reinicios.

- Actor 33, combate 494024632, conexión `5a603a985c7942b18838d87d2b72f1d2`, boot `dc583afce5ec4d15a11520891340773c`.
- Última Sacudida: servidor 02:34:19.724745 UTC; cliente muestra lanzamiento y daño −4 a las 21:34:20.676/681 locales. Los IDs entregados son distintos (216–224).
- Última acción de combate recibida: 13337 ID247 y 13482 ID248, seguida de cierre 13420 a las 02:35:17.597636. ACK de turno 33 enviado a las 02:35:17.443745; request finalizado a las 02:35:17.682763.
- Servidor registra EOFError a las 02:35:28.119194. `receive()` sólo produce este error si `recv()` devuelve bytes vacíos; un timeout produce otro flujo.
- Último frame recibido: movimiento de mundo 13852 a las 02:35:28.120647. Canal Netty pasa a inactive a las 02:35:28.148583; log cliente connection lost a las 21:35:28.150 y razón genérica 0.
- No paquete de muerte/victoria ni excepción de script aES en esta ventana. Se guardó HP250; NPCHP505, ganador null, combate activo. El cierre no equivale a victoria.

Los logs no identifican quién inició el cierre TCP/TLS. El agente sólo registra inactive, no la pila del primer close/disconnect saliente. No hay base para atribuirlo al carrier, a IDs, a la animación o a una decisión de usuario. Los errores de elementos interactivos ocurren antes, a las 21:34:09; no son una excepción en el momento de desconexión. Las excepciones HTTP BrokenPipe de la ventana pertenecen a peticiones API distintas y no acreditan causa del socket de juego.

Próximo diagnóstico preciso: capturar FIN/RST por extremos y/o stack del primer close/disconnect del canal Netty. Eso distinguirá cierre cliente, red/intermediario y cierre servidor sin inventar ACK ni introducir esperas.

Evidencia privada preservada: `.runtime/local/state-carrier-disconnect-packets.json`, `state-carrier-disconnect-lifecycle.json`, `state-carrier-disconnect-server.json`, `state-carrier-disconnect-client-log.txt`. No contienen una prueba de causa raíz.

## Instrumentación preparada para la siguiente reproducción

`sniffer/java/CaptureAgent.java` lifecycle_version2 instrumenta los métodos originales `AbstractChannelHandlerContext.invokeClose/invokeDisconnect` y `AbstractChannel$AbstractUnsafe.close/doClose0/closeForcibly/disconnect`. Cada canal registra `first_close=true` sólo una vez, con hilo, clase/método/línea y tipo de excepción; no captura mensajes de excepción, variables locales ni contenido de objetos. También conserva la pila de inactive. No modifica el flujo Netty ni añade ACK/esperas.

La JVM ya abierta conserva su agente anterior. La siguiente JVM propia se lanza mediante `bash client-tools/local-client.sh --profile state-carrier-test` (el launcher compila el agente automáticamente); no requiere reiniciar world. Confirmar en events.jsonl `capture_start.lifecycle_version=2` y hooks_installed para las dos clases Netty. Coordinar el relanzamiento con el dueño del perfil; no utilizar agent-spell-test, actualmente utilizado por el usuario.

Probe durable `sniffer/java/ProbeCaptureCloseLifecycle.java`: EmbeddedChannel con dos IDs distintos, uno cerrado por pipeline y otro directamente por unsafe. Compilación y ejecución con javaagent PASS; verificación del JSON confirma dos first_close, exactamente uno por canal, y pilas que incluyen el llamador del probe. No conexión de juego ni gráficos.

Como segunda perspectiva opcional, `bash sniffer/capture-game-close-flags.sh lo0 .runtime/local/state-carrier-fin-rst.txt` registra sólo líneas TCP FIN/RST del puerto15556, sin volcado de payload ni pcap. Requiere permiso de captura de la interfaz; si tcpdump lo rechaza, no altera permisos ni servicios. Detener con Ctrl-C tras el incidente. Las direcciones/puertos y flags permiten identificar el extremo emisor del FIN/RST; la pila Netty distingue la ruta de cierre de la aplicación. No se ha ejecutado una nueva reproducción ni obtenido FIN/RST real todavía.

## Discriminación causal del servidor

Lectura del contrato actual:

| Ruta | Contrato | Evidencia necesaria |
|---|---|---|
| Lease expirado/reemplazado en idle | Comprueba generación/expiry; heartbeat cada10s extiende TTL60s. False produce ValueError `Session expired or replaced`. | Detail/traceback de disconnected; no equivale a EOF. |
| Checkpoint stale | Validación de lease SQLite; ValueError `Fight checkpoint session is stale`. | Traceback y detail; no corta directamente socket. |
| Timeout de lectura1s | Invoca idle y reintenta mientras válido. | No representa por sí solo desconexión ni EOF. |
| EOF TLS | recv devuelve bytes vacíos; receive lanza EOFError. wrap_socket usa supresión por defecto de ragged EOF, por lo que no prueba close_notify TLS limpio. | Stack receive y perspectiva de FIN/RST/close cliente. |
| Takeover por nueva autenticación | begin_session reemplaza generación y hace shutdown(SHUT_RDWR) del socket previo desde otro worker. | Nueva account_authenticated correlacionada y motivo de shutdown previo. |
| Fallo broadcast World._send | Captura OSError y hace peer.shutdown(2); el worker lector puede ver EOF como consecuencia. | Actualmente no hay log de causa en _send; EOF solo no permite descartarlo. |
| Apagado Connections.drain | Envía opcode18/reason16 y después SHUT_WR. | Notice y logs de shutdown/boot; no aparecen en esta ventana. |

No se encontró nueva autenticación ni nueva conexión TLS en los eventos02:30–02:39 del incidente. No aparece aviso18. Eso no identifica el iniciador del cierre: la ruta _send carecía de registro causal. Los nuevos campos traceback/state/counters en disconnected permiten distinguir errores directos de receive/send/idle, pero un shutdown desde otro worker todavía requiere registro en ese punto.

Nueva captura del perfil propio confirmada a las03:01:55UTC: lifecycle_version2 y hooks instalados para AbstractUnsafe y AbstractChannelHandlerContext; todavía sin first_close al comprobarla. No se hicieron clicks ni cambios de motor.
