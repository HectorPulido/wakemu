# 13. Mensajes privados y otros canales de chat

Enrutar cada mensaje solo a los destinatarios del canal correspondiente.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

15, 24, 32. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Un privado nunca usa broadcast; solo destinatarios autorizados reciben el contenido.

- [Contratos nativos de ocho canales, defecto de gremio y routing actual](REVISION-RESPUESTAS.md).
