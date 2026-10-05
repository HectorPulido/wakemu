# Diagnóstico — 6

## Contexto registrado

**Confirmado:** `planting_runtime.py::mature` consulta solo `stage=1` y, para plantas, avanza únicamente a `2` si existe. No recorre todas las etapas del catálogo. Además, los errores de SQLite pueden impedir incluso esa transición.

**Posible solución:** identificar las etapas de la referencia concreta y programar cada transición válida con su fecha persistida y notificación. No asumir que todas las especies usan etapas consecutivas. **Validación:** recorrer todas las fases y reconectar entre ellas.

## Lectura actual

La consulta selecciona stage=1 y el avance vegetal explícito llega a stage=2. No existe en esta función una cadena genérica hasta toda etapa final del catálogo.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Etapas/duraciones exactas de la referencia Cardo.
- Efecto del clima en cada etapa y semántica de pausa/catch-up.
- Formato de actualización y regla al cosechar una planta parcialmente madura.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
