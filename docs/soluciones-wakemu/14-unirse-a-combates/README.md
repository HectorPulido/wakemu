# 14. No se puede entrar al combate de otra persona

## Corrección de colocación multijugador — 9 de octubre

Corregidos el registro nativo del jugador que se une y la desconexión al
rendirse durante colocación. Evidencia automática y aceptación manual:
[informe de registro y rendición](../../reports/combat-inventory/multiplayer-placement-registration-20261009.md).
La aceptación visual con ambos clientes sigue pendiente.

Unir jugadores durante colocación a un encuentro compartido ya existente.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

12, 15, 16, 18, 31, 33, 34. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Todas las sesiones ven un único encuentro; entrar tarde no altera sus actores ni su turno.

[Servicio compartido, solicitud nativa y límites](REVISION-RESPUESTAS.md).

## Revisión de integración — 7 de octubre

**En revisión.** El codec13241 y `combat_shared.Registry.join()` validan colocación, mapa/instancia, equipo, celda libre y ownership. El dispatcher todavía conserva combate por conexión y no conecta esta ruta. La capa PostgreSQL ahora registra miembros con generación, comparte el checkpoint con control CAS, cerca takeover de sesión y liquida recompensas de todos los participantes en una transacción idempotente. El gate aislado pasó 43 pruebas de almacenamiento, recompensas y cierre. Esto no certifica interacción TLS ni integración del dispatcher; el issue sigue abierto hasta probar dos clientes y retorno en juego. No se han modificado el motor ni el mundo activo por este issue.

La aceptación requiere dos clientes en un combate compartido, colocación y turnos coherentes, recompensas individuales idempotentes, desconexión/reconexión y retorno sin bloqueo. Los espectadores se siguen en16.

Recorrido manual conjunto listo para la imagen integrada: [aceptación completa de entrada, observación, rendición y resincronización de mapa](../16-espectadores-y-marcadores/PRUEBA-COMPLETA-14-16-33-MAPA.md).

Para probar tres combatientes en un único PvE, con dos entradas sucesivas durante colocación, retirada del líder y victoria de los compañeros, sigue la [aceptación manual TLS de tres jugadores](PRUEBA-MANUAL-TRES-JUGADORES.md). Es un plan de aceptación; no implica que se haya ejecutado contra la imagen activa.

## Autoridad compartida probada en fuente

Migración052 y servicios de membresía/checkpoint/cierre compartido:43 pruebas PostgreSQL aprobadas. Incluyen fence de generación por participante, takeover explícito antes de finalizar desde una sesión nueva, finalizadores concurrentes y premios de miembros desconectados. Las rutas de red compartidas y su aceptación TLS siguen pendientes. Esta migración está excluida de la candidata de objetos78e8ae29 y del mundo activo.

## Integración compartida en fuente

Entrada 13241, colocación, readiness, acciones y barrera de ACK conectadas al adapter compartido. Logout conserva el combate de los compañeros y libera el buffer de posición. Falta completar settlement por roster y reports privados por dueño: la ruta anterior `prepare_finish()` por conexión no acredita premios para todos. Estos cambios no están en la imagen activa; falta gate completo con dos clientes TLS y regresiones de combate individual antes de desplegar.

## Cierre y publicación multiusuario en fuente

Settlement por roster conectado a una transacción; reports privados por dueño, Registry retenido hasta retornos y takeover de generación nueva tras reconexión. Los callbacks SQL no retienen lock global y un peer roto no impide publicar al otro. Gates fuente65/65 single+shared y61/61 PostgreSQL/shared/World aprobados. Push de resultados al compañero quieto implementado; falta concluir el smoke real TLS de dos clientes. No desplegado.

## Avance del smoke TLS compartido

La candidata aislada completó una pelea con dos propietarios (fight4; owners13/14): ambos recibieron `12755` (159 y126 bytes); el segundo cliente recibió el resumen mediante push. El harness permite ACKs de turnos y acciones previas del segundo cliente; la medición de ausencia de solicitudes entre el golpe final y el resumen debe acreditarse explícitamente. La ejecución detectó y permitió corregir tres defectos de integración en fuente: arranque del turno NPC con el driver existente, activación del settlement al terminar acciones compartidas y doble envoltorio del paquete de equipo en el resolver de loot. La comprobación de persistencia de ambos propietarios sigue en curso. Esto no acredita despliegue: la imagen activa `ff2659e9` integra IA y debe conservarse al integrar los cambios de combate compartido.

La revisión del harness detectó un límite de evidencia: `idle_peer_received_without_request` estaba escrito como constante y los ACKs de turnos de B ocurrían después de listo. Se está reemplazando por contadores reales de paquetes enviados antes del golpe final y al recibir el resumen. Los recibos PostgreSQL y el cierre de ambos participantes siguen acreditados; no se afirma ausencia total de solicitudes durante la pelea.

## Regresión encontrada al subir de nivel en settlement compartido

La revisión del callback encontró que `shared_loot` vuelve a cargar el personaje después de `award_shared_member`. `build_drop_context` llama `build_context`, que exige igualdad entre el nivel efectivo del actor del combate y el de la hoja: si el premio sube de nivel, esa recarga usa el nivel nuevo y puede rechazar el cierre. El smoke previo con44/45XP no subió niveles, por lo que no cubría esta transición. La corrección debe congelar el contexto de drops antes del premio sin debilitar la validación de propiedad/nivel. Gate de subida1→2 y nuevo smoke pendientes; candidata integrada no desplegada. La comparación del smoke individual original pasó en base6319 con SDK de IA y tiempos de lectura suficientes.


### Corrección verificada de recompensas al subir de nivel

La candidata `4212471c076e24c33fb84de31d41a208dec18cf03c098fe818223b5bca56e0a3` congela contextos de recompensa y drops antes de acreditar XP. Gate PostgreSQL76/76; TLS individual con personaje nuevo sin comando de nivel y TLS compartido aprobados. Ambos propietarios subieron de1 a8, con14365XP y5kamas por propietario persistidos. El contador del segundo cliente registró únicamente13510 (ACK obligatorio), sin solicitudes de juego, mientras recibió el resumen por push. Replay tras reconectar y retorno de ambos aprobados. Evidencia privada: `.runtime/local/shared-levelup-gate-20261007.txt`. Sigue sin desplegar; falta verificar la imagen integrada con clima y encantamiento.


### Despliegue integrado verificado

Imagen `e839fd35a2c123b8c83006528cfabc8f7bb5c8e5c3d0973f347ffcadc5321742` desplegada en world; Docker healthy y `/health` PostgreSQL correcto. Migraciones057–059 aplicadas;388 patrones de sublimación en SQL. Gate de la imagen198/198 aprobado y TLS de combate individual/compartido, sublimaciones y clima acreditados. Respaldo previo privado `.runtime/backups/pre-integrated-20261007.dump`, archivo CUSTOM con793 entradas TOC. Aceptación visual pendiente; no implica cierre completo del issue.

## Unión después de retirada del iniciador: en revisión

El cliente conserva los líderes originales del marcador. Tras el ACK de retirada, el índice de actores del servidor deja de resolver ese líder, aunque el equipo siga en colocación. Se implementa un alias limitado al líder original de PvE y al mismo equipo, condicionado a colocación, participante controlado superviviente y capacidad. No se retira/recrea el marcador:12238 limpia el combate externo y13753 rechaza IDs duplicados. Pendientes pruebas de permisos, fase y eliminación del alias al finalizar; todavía no está instalado.
