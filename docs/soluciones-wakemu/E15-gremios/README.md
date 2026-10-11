# E15 — Sistema completo de gremios

## Alcance solicitado

Investigar cómo crear un gremio y mantenerlo de forma persistente. Auditar creación, nombre y emblema, requisitos y coste, identidad estable, fundador, invitación y aceptación, miembros, rangos y permisos, expulsión y salida, cambio de líder, disolución, progresión y bonus cuando existan en esta versión. Incluir interfaz, chat, cofres, tesorería, merkamundo, errores, reconexión, reinicio y coexistencia de dos jugadores.

## Evidencia actual

**Handoff — 2026-10-10:** [remaining work and deployment prerequisites](PENDING-20261010.md) · [detailed full manual acceptance guide](MANUAL-ACCEPTANCE-20261010.md). Development is handed back pending Hector’s test feedback; nothing was deployed by this work.

**2026-10-10 — Guild shared chest:** [implementation, migration 106 and full acceptance battery](GUILD-CHEST-IMPLEMENTATION-20261010.md). Deposits, withdrawals, compartment moves, permissions, custody metadata and native viewer updates are implemented offline. PostgreSQL/live validation remains pending. Haven Worlds are deferred at the user’s request.

**2026-10-10 — Offline implementation:** [code, migration, test batteries and remaining integrations](IMPLEMENTATION-20261010.md). The core guild domain, native dispatcher, snapshots, chat and economic backend now exist. Migration 101 is not applied and the feature remains disabled. Full E15 is not declared playable; live validation, deferred Haven Worlds and several bonus/policy contracts remain pending.

El [modelo y la persistencia](MODELO-Y-PERSISTENCIA.md) documentan campos protobuf de gremio, miembros, rangos y bonus; restauración local y remota; transporte de deltas; 27 permisos y 1.080 casos de jerarquía ejecutados con consumidores nativos. La [revisión técnica](REVISION-RESPUESTAS.md) conserva además el contrato de creación, requisitos mostrados por la interfaz, nombre, emblema y confirmación. Son pruebas de contratos con fixtures, no creación ni persistencia real de un gremio.

Se conserva también el [probe histórico del decoder de chat](probe-decoder-actual.json). Antes de esta implementación, la búsqueda dirigida no encontró referencias de gremio en `storage/store.py`, `local_game_server.py` ni `protocol_codec.py`; esto no prueba ausencia en todos los módulos.

## Investigación previa y validación pendiente

Revisión previa a la implementación offline del 10 de octubre: [plan de implementación y brechas actuales](IMPLEMENTATION-READINESS-20261010.md). En esa revisión todavía no existían el dominio/esquema de gremios ni los handlers, y se reprodujo el fallo del decoder 13744; el código posterior corrige esos puntos. El transporte local ya tiene una ruta `15548/format22` usada al cambiar de héroe; falta validar e integrar el modelo no vacío y la carga inicial, preservando esa sincronización.

Completar invitación/aceptación, salida/expulsión, transferencia de liderazgo, disolución, progresión, bonus y servicios de gremio; cotejar cada solicitud con dispatcher, almacenamiento y respuesta. Resolver normalización/unicidad de nombre, significado de `ownerId`, unidades de fechas y transporte del bootstrap. El modelo propone tablas concretas y transacciones para creación/coste, miembros y permisos; la implementación posterior está enlazada arriba; la validación PostgreSQL y de durabilidad continúa pendiente.

Cuando los contratos y requisitos estén preparados, crear un gremio exclusivo de auditoría con dos personajes: creación, invitación, aceptación/rechazo, permisos, chat, salida/expulsión y reconexión. Comprobar SQL y estado visible antes/después; reiniciar únicamente la instancia propia autorizada para verificar durabilidad. Estas pruebas funcionales todavía no se han ejecutado.

La investigación original no implementó fixes; la implementación offline posterior está documentada arriba. El chat es un subsistema de este issue; [E13](../E13-canales-de-chat/README.md) conserva la auditoría general de canales.
