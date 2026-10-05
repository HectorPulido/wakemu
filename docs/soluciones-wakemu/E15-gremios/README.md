# E15 — Sistema completo de gremios

## Alcance solicitado

Investigar cómo crear un gremio y mantenerlo de forma persistente. Auditar creación, nombre y emblema, requisitos y coste, identidad estable, fundador, invitación y aceptación, miembros, rangos y permisos, expulsión y salida, cambio de líder, disolución, progresión y bonus cuando existan en esta versión. Incluir interfaz, chat, cofres, tesorería, merkamundo, errores, reconexión, reinicio y coexistencia de dos jugadores.

## Evidencia actual

El [modelo y la persistencia](MODELO-Y-PERSISTENCIA.md) documentan campos protobuf de gremio, miembros, rangos y bonus; restauración local y remota; transporte de deltas; 27 permisos y 1.080 casos de jerarquía ejecutados con consumidores nativos. La [revisión técnica](REVISION-RESPUESTAS.md) conserva además el contrato de creación, requisitos mostrados por la interfaz, nombre, emblema y confirmación. Son pruebas de contratos con fixtures, no creación ni persistencia real de un gremio.

Se conserva también el [probe del decoder de chat](probe-decoder-actual.json). La búsqueda dirigida no encontró referencias de gremio en `storage/store.py`, `local_game_server.py` ni `protocol_codec.py`; esto no prueba ausencia en todos los módulos.

## Investigación y propuesta pendientes

Completar invitación/aceptación, salida/expulsión, transferencia de liderazgo, disolución, progresión, bonus y servicios de gremio; cotejar cada solicitud con dispatcher, almacenamiento y respuesta. Resolver normalización/unicidad de nombre, significado de `ownerId`, unidades de fechas y transporte del bootstrap. El modelo propone tablas concretas y transacciones para creación/coste, miembros y permisos; esas propuestas siguen sin implementación ni validación de durabilidad.

Cuando los contratos y requisitos estén preparados, crear un gremio exclusivo de auditoría con dos personajes: creación, invitación, aceptación/rechazo, permisos, chat, salida/expulsión y reconexión. Comprobar SQL y estado visible antes/después; reiniciar únicamente la instancia propia autorizada para verificar durabilidad. Estas pruebas funcionales todavía no se han ejecutado.

No se implementaron fixes. El chat es un subsistema de este issue; [E13](../E13-canales-de-chat/README.md) conserva la auditoría general de canales.
