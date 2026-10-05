# E13 — Canales de chat en general

## Alcance

Por aclaración del usuario, E13 abarca los canales en general. General funciona en la prueba manual; no se extiende ese resultado a privado, grupo, comercio, reclutamiento ni otros canales. [E15](../E15-gremios/README.md) investiga el sistema completo de gremios: creación, persistencia, miembros, rangos, permisos y servicios, incluyendo su chat.

## Evidencia disponible

El [issue 13 original](../13-chat-privado-y-canales/README.md) conserva el cotejo de solicitudes y respuestas nativas, identificadores de canales, consumidores y pruebas manuales con dos clientes. [Probe de contratos](../13-chat-privado-y-canales/probe-canales-nativos.json): decodificar una solicitud correctamente no acredita handler, permisos, destinatarios ni recepción visible. El privado enviado por el usuario no produjo mensaje ni error; General sí funcionó.

## Trabajo pendiente y solución del servidor

Completar una matriz por canal: opcode y cuerpo, autorización, alcance de destinatarios, respuesta nativa, error visible, límites en DB y resultado entre dos personajes de auditoría. Comprobar recepción y ausencia de filtraciones entre mapas, grupos o identidades; incluir desconexión y cambio de sesión. Implementar posteriormente routing y handlers por contrato, con membresía autoritativa para canales restringidos. No reutilizar números de canales o cuerpos de General sin cotejar su consumidor.

No hay fixes aplicados ni declaración de funcionalidad de todos los canales.
