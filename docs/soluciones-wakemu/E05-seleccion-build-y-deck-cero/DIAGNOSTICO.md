# Diagnóstico — E05

## Contexto registrado

Store.character no carga una selección activa; build_set emite índice activo 0. Existen consumidores de estadísticas y combate que usan 0 por defecto. La reentrada observada vuelve a la predeterminada.

## Lectura actual

El campo inicial de selección se emite como proto_field(8,0). Guardar blobs no cambia esa autoridad. Hay que enlazar persistencia, serialización y consumidores efectivos.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Autoridad y formato persistido de selección y revisión.
- Política de edición y activación durante combate.
- Carrier nativo de selección y fallback tras borrado.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
