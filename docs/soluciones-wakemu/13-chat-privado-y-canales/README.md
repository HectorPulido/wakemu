# 13. Mensajes privados y otros canales de chat

Enrutar cada mensaje solo a los destinatarios del canal correspondiente.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Avance en fuente — 2026-10-07: migración039 y autoridad PostgreSQL para contactos, ignorados y DND. Handlers784/657/672/799/12449 y bootstrap630 conectados; las altas resuelven el nombre de personaje que realmente envía el cliente, sin inferir un personaje principal de la cuenta. Gate aislado de contactos/dispatch/codec24/24. El routing privado consulta una política de bloqueo fuera del lock de membresía: códigos nativos349/102 y349/103, sin entrega ni eco del contenido; gate World/wire55/55. La imagen0996b53 pasó405 pruebas con fuentes/protocolos/migraciones internos y PostgreSQL aislado, incluyendo estas ramas e inventario/intercambio/sesiones. Payload nativo349/102–103 corregido con nombre de destinatario. Ampliación incluida en la imagen047729d7 activa: gate259 y entrada TLS/contactos/DND aprobados. No se acredita todavía aceptación del cliente para esta ampliación.

Implementación parcial del **servidor**: request13917 enruta privados mediante respuestas720 y errores349, sin broadcast. El gate inicial de protocolo, routing y sesiones pasó93 pruebas; el gate posterior de cierre de sesión/Redis/chat pasó88 pruebas, incluyendo consultas y envíos fuera del bloqueo global. Los gates tienen cobertura solapada y no se suman. Véase el [cotejo actual PostgreSQL](COTEJO-ACTUAL-POSTGRESQL.md). Recepción visual de privados confirmada por el usuario el 6 de octubre. Quedan preferencias de privacidad y otros canales; el issue completo sigue **Solucionado parcialmente**.

## Dependencias

15, 24, 32. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Un privado nunca usa broadcast; solo destinatarios autorizados reciben el contenido.

- [Contratos nativos de ocho canales, defecto de gremio y routing actual](REVISION-RESPUESTAS.md).

## Aceptación manual de privados — 6 de octubre

El usuario confirma funcionamiento entre dos clientes. Las capturas muestran recepción de «Audiluna: hola», eco «a Audiluna: mundo», error nativo «El jugador "Audiluna" no existe o no está conectado» al desconectarse y recepción «Prueba Oficios: krakatoa» en una pestaña privada tras reconectar. Esta evidencia acredita envío, respuesta, rechazo offline y recepción posterior; no acredita aislamiento ante un tercer observador ni los canales de grupo, comercio o reclutamiento. No se modificó el cliente.


## Canales y permisos aportados por el usuario — 6 de octubre

La captura [canales-chat.png](canales-chat.png) y las notas en PRUEBAS.md completan la lista visible. Local `/l`, privado `/w`; comercio `/m`, comunidad española `/c` y reclutamiento español `/r` permiten escribir a cualquier jugador. Grupo `/p` requiere pertenecer a un grupo y gremio `/g` a un gremio. Información (juego) e Información (combate) solo reciben mensajes del sistema; Conversación ANKAMA `/d` solo admite emisores administradores, con recepción para todos. Política y Campo JcJ `/b` aparecen en la interfaz: sus permisos/alcance quedan por cotejar, sin asumir que sean canales generales.

Esta aportación especifica los permisos esperados; no acredita que el servidor ya enrute todos esos canales. El issue permanece Solucionado parcialmente. El lote de ecología034 ya utiliza Información (juego) mediante notificación nativa349/subtipo4; eso no sustituye la implementación de comercio, comunidad o reclutamiento.

## Canales conectados en fuente — 2026-10-06

Comercio13074→626, grupo13224→606, reclutamiento13188→769 y comunidad13831→655 ya tienen dispatcher. Identidad de cuenta remitente y metadatos se obtienen de sesión/SQL; grupo se valida contra membresía PostgreSQL y no emite a terceros. Públicos se enrutan entre mapas; comunidad/reclutamiento filtran idioma0FR/1EN/2ES/3PT. SQL036 parametriza idioma por defecto, comunidad, bytes máximos e intervalo mínimo; preferencias por cuenta opcionales. No se ejecutan comandos de pruebas a través de estos canales.

El decoder13224 conserva el ID antes del texto, como muestra `cmt.aWH`→`cmq.d`; una interpretación inicial de orden inverso se descartó tras revisar el serializador. Imagen7289b2de construida, pruebas/gate y despliegue pendientes. Gremio depende de membresía autoritativa aún pendiente enE15; no se lo declara resuelto por esta integración. El descriptor nativo diferencia `/d` intergame (protobuf) de `/a` o `/admin` (12116 y permisoADMIN_CHAT); esa diferencia requiere routing propio, no sustituir `/d` por un broadcast administrador.

Despliegue2026-10-06:imagen7289b2de,SQL036,gate430 OK sin mounts fuente/protocolos/migraciones. Comercio, grupo, reclutamiento y comunidad confirmados por el usuario. El issue sigue parcial por alcance de gremio/intergame/admin/política/JcJ y privacidad.

Postdespliegue:Dockerhealthy,listeners15556/15558/18081 verificados;runtime confirma políticaSQL036 (idiomas6/comunidad4,2048bytes,intervalo200ms).

## Aceptación de canales públicos — 2026-10-06

El usuario confirma «todo funcionó perfecto sobre el chat» tras la [prueba completa de canales públicos](PRUEBA-CANALES-PUBLICOS.md): comercio/m, comunidad española/c y reclutamiento español/r en ambas direcciones, mismo mapa, mapas distintos y regreso desde selector. Privados y grupo cuentan con aceptación anterior independiente. Estas ramas quedan confirmadas; el issue13 conserva **Solucionado parcialmente** por gremio, intergame/admin, política/JcJ y privacidad adicional todavía pendientes.
