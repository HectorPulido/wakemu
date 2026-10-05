# Diagnóstico — E02

## Contexto registrado

synchronization devuelve13713 + identidad + bags; el parser cwY/chK entrega el resto a biB.as, que requiere entidad. Capturas y logs del bolso demuestran desalineación, underflow, campos absurdos y mapa negro. Puede afectar a otros rechazos que reutilicen esa función.

## Lectura actual

La misma función de resync incorrecta es reutilizable por rechazos de inventario. Auditar todos sus callers y probar parser de entidad; arreglar solo equipar bolso dejaría otras rutas expuestas.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Serializer/campos de entidad completos y carrier alternativo verificado.
- Listado definitivo de callsites según versión actual.
- Orden seguro para entidad ya cargada ybloqueos GUI.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
