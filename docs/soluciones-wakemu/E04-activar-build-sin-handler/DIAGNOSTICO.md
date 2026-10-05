# Diagnóstico — E04

## Contexto registrado

Prueba gráfica a las 18:09:57 UTC con AuditComplete de nivel 100: petición de 9 bytes rechazada por falta de handler. El check local Activa no demuestra activación autoritativa.

## Lectura actual

Este decoder maneja guardado 12772 de cuatro blobs, no la petición 13776 de 9 bytes. No usarlo para activar; el rechazo en vivo confirma la falta de esa ruta.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Respuesta exacta y liberación del bloqueo nativo.
- Política de activación durante combate y de salud.
- Identidad/revisión de operación para reintentos.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
