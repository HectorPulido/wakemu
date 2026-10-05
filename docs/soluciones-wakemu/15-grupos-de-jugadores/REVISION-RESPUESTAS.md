# Grupos: invitación, roster y cupo nativos

## Contratos encontrados y ejecutados

La UI `cMv.openInviteDialog` llama `bxI.nI`. `PartyInvitationCommand` y el gestor usan invitación genérica `Or`, opcode **1156**, tipo `fCz.PARTY=1`. Hay destinatario por nombre y por ID numérico. Se ejecutaron ambos encoders con nombre AuditDos o ID12345.

El cuerpo empieza por byte tipo, dos i64 de contexto (`baC/baF`), luego selector de destinatario:0→u8longitud/nombre UTF8;1→i64ID. Los dos campos de contexto quedaron0 en el fixture: **no se deduce que deban ser siempre cero**, falta cotejar sus setters/casos. Los frames emitidos tienen categoría6 con `baA` nativo por defecto; el encoder contempla categoría2 con el flag falso. No enviarlos como frames de categoría3 sin cotejar el mux/servicio de invitaciones.

`bxI.kP/kQ` construyen **Ou1074 y Ov1066**, respectivamente, con dos i64: ID del grupo (`fgq.Sn`) y miembro destino. Se ejecutaron fixtures grupo456/miembro12345. Todavía no se atribuye expulsión/traspaso de líder a cada opcode sin cotejar callers y consumidores; compartir layout no implica compartir autorización.

`cMv.leaveParty` emite evento local16130 a `aAk`: **16130 no es un opcode de red acreditado**. Hay que seguir su handler hasta el mensaje final, evitando implementar ese número como request del servidor.

## Límite y representación

`fgq` tiene ID de grupo, identidad del líder y mapa de miembros `fga`. `isFull()` compara el tamaño del mapa con configuración `eEL.PARTY_MAX_MEMBERS` (ID629, key `party.max.members`, default **6**). Es un límite configurable del roster, no seis cuentas por definición. Falta comprobar qué identidades añaden héroes y compañeros y cómo cuenta cada controlador.

El servidor mantiene `World.players` por personaje/mapa/instancia y `COMBAT_GROUPS` para monstruos; ninguno proporciona este roster de party. `characters/social.py` inicializa secciones sociales, pero no invita ni sincroniza miembros.1156/1074/1066 no tienen handlers en el dispatcher inspeccionado. Chat13224 lleva group_id, pero tampoco crea membresía.

## Solución concreta del servidor

Separar autoridad de party y controlador: group_id, leader_character_id, miembros/identidades, propietarios/generaciones y revisión. Resolver invitación por nombre o ID contra sesiones del mundo; guardar destinatario/tipo/contexto, evitar autoaceptación y revalidar cupo al aceptar —dos invitaciones concurrentes no deben sobrepasarlo—. No confiar en group_id/miembro remitidos: comprobar autoría y permiso según cada operación.

Emitir snapshot/deltas nativos de roster a todos los miembros, actualizar el campo de party de cada personaje y publicar invalidación al salir/desconectar. Cotejar la política real de liderazgo antes de elegir sucesor. Chat13224 autoriza contra este roster y entrega a miembros, aunque estén en mapas distintos si el contrato lo permite; no reutilizar broadcast de ubicación.

Combates y mazmorras consultan party como autoridad de admisión, manteniendo su propia membresía de encuentro/instancia. No sacar al personaje de un combate por borrar una entrada del roster sin revisar el ciclo nativo. La UI de salida incluye texto de imposibilidad en combate; eso no demuestra por sí solo la regla completa del servidor.

## Héroes y compañeros: investigación pendiente

El usuario pidió cotejo de código e internet. Se buscó información oficial, pero la búsqueda devolvió guías secundarias; no se adoptaron límites ni políticas técnicas de esas guías. El default6 aquí procede del código instalado. Falta verificar cupo por controlador, elegibilidad de compañía y representación de héroes/compañeros en roster y combate con fuentes nativas/oficiales de la versión.

## Límite de reproducción

No se aceptó una invitación ni se formó party entre dos clientes. Faltan respuesta, expiración/rechazo, snapshot y deltas, opcode final de salida, permisos de1074/1066 y recuperación de desconexión. [Frames sintéticos, default/config y hashes](probe-invitaciones-y-cupo.json).
