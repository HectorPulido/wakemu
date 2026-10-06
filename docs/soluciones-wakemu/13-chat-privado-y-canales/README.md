# 13. Mensajes privados y otros canales de chat

Enrutar cada mensaje solo a los destinatarios del canal correspondiente.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Implementación parcial del **servidor**: request13917 enruta privados mediante respuestas720 y errores349, sin broadcast. El gate inicial de protocolo, routing y sesiones pasó93 pruebas; el gate posterior de cierre de sesión/Redis/chat pasó88 pruebas, incluyendo consultas y envíos fuera del bloqueo global. Los gates tienen cobertura solapada y no se suman. Véase el [cotejo actual PostgreSQL](COTEJO-ACTUAL-POSTGRESQL.md). Quedan recepción visual entre clientes, preferencias de privacidad y otros canales; el issue no se declara cerrado.

## Dependencias

15, 24, 32. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Un privado nunca usa broadcast; solo destinatarios autorizados reciben el contenido.

- [Contratos nativos de ocho canales, defecto de gremio y routing actual](REVISION-RESPUESTAS.md).
