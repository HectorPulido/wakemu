# Diagnóstico — E08

## Contexto registrado

UI nivel100 muestra Builds(1/24); builds.validate solo acepta índices0..2. Índice3 rechazado en pruebas de ambos backends. No se reprodujo una creación gráfica hasta ese límite; falta verificar configuración nativa y correspondencia de slots.

## Lectura actual

La guarda exige índice entero entre 0 y 2. El cupo visible de 24 es incoherente con esa frontera; su significado nativo sigue pendiente y no justifica ampliar ciegamente el rango.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Significado de 24 y feature/config nativa asociada.
- Cupo deseado por nivel y máximo de todos los codecs.
- Política de indiceslegacy fuera del límite elegido.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
