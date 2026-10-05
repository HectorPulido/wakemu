# Diagnóstico — 24

## Contexto registrado

**Confirmado parcialmente:** `wire.py` fuerza las secciones de nación propia a cero y limpia sincronización nacional. Esto contradice que el servidor elija Amakna deliberadamente en esas secciones, pero no descarta otra sección del replay, item inicial o caché.

Lo mas probable es que este quemado en alguna parte del buffer, hay que revisar donde

**Posible solución:** identificar si el pasaporte es un objeto o estado de nación, localizar su origen y sustituir cualquier dato heredado por estado propio. **Validación:** personaje nuevo con perfil limpio y reconexión; no borrar datos personales como sustituto de modelar nación.

Identificado ademas que cada lugar tiene asignada una nacion de por defecto hay que forzar que los lugares no tengan alineamiento hasta el momento que hagamos esa mecanica

## Lectura actual

Revisar defaults de creación junto con bootstrap: eliminar visualmente un pasaporte no define ciudadanía ni neutralidad de territorios. La propuesta necesita separar nación, permisos y UI.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Qué widget/objeto representa el pasaporte y referencia si es item.
- Identificador neutral para cada carrier nacional/territorial.
- Alcance de neutralizar datos antiguos sin destruir ciudadanía futura.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
