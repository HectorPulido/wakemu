# Diagnóstico — E06

## Contexto registrado

En la copia fija: guardar aptitudes válidas con nivel fijo 49 y ejecutar !nivel50 produce Invalid aptitude sheet level después de confirmar nivel/XP. SQL queda nivel50 y HP/max540, en vez de550. Ocurre también la incompatibilidad al hidratar journal; no es pérdida de puntos probada en todos los casos.

## Lectura actual

La validación de hojas depende del nivel actual. La subida de nivel y la hidratación deben validar coherencia antes de commits separados; el ensayo fijo 49→50 confirmó persistencia parcial.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Semántica de hoja limitada/modulada en esta versión.
- Autoridad para nivel y hojas pendientes y garantía multi-storage.
- Estados históricos afectados y política de HP parcial al migrar.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
