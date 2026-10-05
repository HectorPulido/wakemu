# Diagnóstico — 16

## Contexto registrado

**Confirmado parcialmente:** hay codec de envolvente externa `13753`, pero no se observó un servicio de espectador conectado a los combates vivos. El replay puede incluir paquetes de la captura inicial y filtra los de otro mapa; no representa un registro de combates actuales.

**Posible solución:** publicar marcadores de los combates propios y una sesión de observación sin control de actores, con snapshot inicial y eventos posteriores. **Validación:** observar inicio, turno y fin sin poder ejecutar acciones del participante.

## Lectura actual

Existe un carrier externo, pero espectar requiere snapshot seguido de eventos ordenados y permisos de solo lectura. No otorgar control de actores al reutilizar join.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Protocolo completo de observar/salir y alcance de 13753.
- Política de privacidad, límites y ACK de observadores.
- Qué efectos deben ser visibles en un snapshot intermedio, no solo replay desde inicio.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
