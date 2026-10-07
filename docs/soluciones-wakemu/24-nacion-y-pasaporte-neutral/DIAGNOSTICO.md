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

## Revisión actual — 7 de octubre

El pasaporte no es un item que haya que localizar: el comando nativo `PassportCommand` abre `passportDialog` y su frame enlaza `pvpLadderEntry` al modelo construido desde la nación del personaje activo. El getter nativo devuelve la nación de ese personaje. El parser qZ reconoce `0` como la nación neutral; el locale muestra ese valor como “Neutral”.

La serialización de personaje ya neutralizaba `NATION_ID`, pero dejaba sin sustituir el byte separado `PASSEPORT_INFO` (offset/longitud salen de `entity-layouts.json`, default `00`). Se añadió ese campo a los defaults vacíos y una prueba de regresión que verifica el reemplazo y conserva los bytes vecinos. Esto corrige un posible residuo de la plantilla; no prueba por sí solo cómo se ve `/passport` en el cliente actual.

La petición de neutralizar “los lugares” sigue sin carrier acreditado. `territory_cells` y los datos de mapa consultados ubican mapas/regiones/celdas; no proporcionan una nación propietaria. `15984` contiene sincronización pública nacional por ID y sus registros formato17 se normalizan, pero eso no demuestra ownership nacional de cada lugar. Mantener ese límite explícito evita borrar datos o asignar un ID de nación a una estructura desconocida.
