> 2026-10-09 22:57 follow-up: repeated challenges failed forever after old pending invitations expired. The retry transaction renewed the quarantine then rolled retirement back. Retirement now anchors to expires_at; actual received replies retain their receipt-time protection. Full duel suite: 29 passed on an isolated PostgreSQL database; combined combat/spectator/harvest suite: 258 passed, no skips. Live acceptance pending. See [investigation and exact retry steps](../../reports/health/DUEL-EXPIRY-RETRY-20261010.md).

# 12. No se puede pelear contra otros personajes

Permitir desafíos consensuados entre personajes sin usar el resolver de grupos NPC.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**En revision; candidata sin desplegar.** Codecs, consentimiento persistente, dispatcher, dos equipos opuestos y retorno sin recompensas están integrados. El ciclo de duelos pasó TLS en la candidata1bc; la candidata posterior afad incorpora la entrada diferida de espectadores. Falta terminar las regresiones de la imagen final y la aceptación visual conjunta.

## Dependencias

14, 15, 18, 31, 33, 34. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Un desafío aceptado crea un combate compartido; control y resultados no dependen del cliente que inició.

## Rechazo reciente y nueva invitación

El rechazo A→B deja una cuarentena local de 60 s para ese mismo sentido; no es cooldown nativo acreditado. El cuerpo13520 no tiene nonce, por lo que una respuesta repetida A→B podría aplicarse a una invitación recién recreada. La invitación inversa B→A no se bloquea por esa cuarentena. El 12708 causa4 es notificación servidor→cliente, no un ACK cliente de cancelar el modal. Evidencia, test y límites en [revisión de respuestas](REVISION-RESPUESTAS.md).

## Avance de autoridad — 7 de octubre

La migración060 conserva PvE como tipo predeterminado y agrega invitaciones y resultado de duelo. `friendly_duel_wire` valida12117/13520 y emite13179/12708; `friendly_duels` ata consentimiento a las generaciones y ubicaciones persistidas, crea participantes en equipos opuestos solo tras aceptar, y liquida el encuentro sin XP, kamas ni botín. La liquidación restaura HP completa y conserva la ubicación capturada; un cierre por desconexión registra al participante desconectado como perdedor. El Registry/adapter tienen una ruta de registro específica para dos propietarios que no reutiliza el `join()` de equipo aliado.

Gate fuente PostgreSQL aislado: **11/11** en `tests.test_friendly_duels`, incluyendo rechazo, expiración, lease sustituido, fallo de preparación con rollback, roster contrario, compensación de Registry antes de publicar, curación/ubicación, ausencia de recibos PvE y replay. Esto valida autoridad y persistencia, no prueba el dispatcher, la presentación de resultado nativa ni el retorno visual. **No desplegado ni probado con clientes TLS.** Esta capa no modifica reglas ni efectos de combate.

## Verificación de integración pendiente

Migración063 separa la restauración de HP del acuse nativo12925: el resultado de un duelo desconectado puede recuperarse antes del acuse, y después no reabre el encuentro. Los retornos PvE nuevos también guardan su acuse; la migración conserva cerrados los retornos PvE históricos. SharedFight declara group_lease=None para que duelos y peleas PvE convivan sin errores de atributo. Gate puro combinado64/64 informado por el agente, incluyendo Registry, colocación y espectadores; PostgreSQL/TLS de esta fuente final aún no ejecutados. Docker dejó de responder bajo carga y el endpoint local health agotó su timeout de3s; no se afirma salud del servicio durante esta incidencia. Prueba manual conjunta preparada en [PRUEBA-GENERAL.md](PRUEBA-GENERAL.md), aún no habilitada.

## Candidata final congelada

Imagen `wakemu-friendly-duel-overlay:20261007-final`, SHA `1bc77bb5cd69acd1df0ec5528dd5484d6c94fae2a9a236480170fb1080d357ce`. Incluye retorno063, group_lease por defecto, marcadores y snapshots territoriales/XP; deja fuera la optimización no relacionada de LOS. Gate de imagen/PostgreSQL:221 casos distintos aprobados. La primera ejecución obtuvo220/221 por una ruta de fixtures incorrecta; el caso de catálogo se repitió y pasó. TLS final aún pendiente. No desplegado.

Cotejo independiente de los contenedores: live e839 tiene209 módulos de combate y candidata1bc tiene218. Los202 módulos comunes restantes son idénticos byte a byte; cambian únicamente `combat_health`, `combat_multiplayer_wire`, `combat_placement_cells`, `combat_rewards`, `combat_shared`, `fight_store` y `combat_session_adapter`, y se agregan9 módulos de duelos/espectadores/política de colocación. LOS y motor de efectos permanecen idénticos. Este cotejo reduce el alcance de revisión; no sustituye regresiones de combate por TLS.

TLS de duelos aprobado en imagen1bc/DB desechable final: rechazo sin pelea, aceptación y Listo inmediatos, desconexión de ambos, HP completa y posición conservada, recuperación del resumen y retorno12925 con nuevas sesiones. Resultado informado: fight_id1, participantes1/2. El TLS separado de espectadores falló por el scope del snapshot; su corrección y el periodo de espera de ACK todavía requieren reconstrucción y regresión integrada. No desplegado.

Repetición de TLS de duelos en la misma imagen1bc: fight3/participantes8 y9, runner cotejado por hash. Verifica en SQL XP/kamas sin cambios, ausencia de recibos de premios/drops, HP completa sin heridas/muerte y misma ubicación; ambos recuperan12755 y retornan12925/13974. Evidencia privada `.runtime/local/duel-final-tls-smoke-20261007.txt`. Los cambios posteriores de entrada pendiente de espectadores aún requieren nueva imagen y regresión.

Copia preventiva del runtime actual preparada antes de cualquier promoción: `.runtime/backups/pre-multiplayer-20261007-1238.dump`, formato CUSTOM,3.2MiB, permisos0600. `pg_restore --list` leído correctamente:822 entradas TOC. Esto acredita que el archivo es legible, no una restauración de prueba. No se ha desplegado la candidata.

## Regresión final y combate compartido

Gate de fuente de300 casos:4 fallos y4 errores. Una comparación independiente con el código congelado del live e839 reproduce exactamente esos8 resultados en28 casos dirigidos; no se atribuyen a la candidata. Se revisan los fixtures y contratos de estas pruebas antes de repetir el gate. Evidencias privadas: `.runtime/local/duel-final-pg-gate-20261007.txt` y `.runtime/local/e839-baseline-audit-20261007.txt`.

El TLS de combate PvE compartido en afad detectó un problema real de persistencia: el segundo socket conserva una revisión local vacía aunque el primer participante ya creó el checkpoint. La validación de revisión rechaza sus guardados. Se está corrigiendo la coordinación de revisiones compartidas, conservando la validación de sesión y participante; la promoción y la prueba manual siguen pendientes.

La corrección de fuente usa una revisión de checkpoint por combate bajo el lock de `SharedFight`; la adopción tardía no puede sobrescribir una revisión más reciente. Verificación local independiente:51/51 pruebas aprobadas de Registry compartido, snapshots, espectadores y lectura TLS fragmentada. Pruebas PostgreSQL preparadas para escritores concurrentes, sesión sustituida, finalización con fallo/reintento e idempotencia terminal; todavía pendientes de ejecución y reconstrucción de imagen.

Gate adicional de la imagen derivada (solo tests montados, código de aplicación congelado):41/41 de checkpoint/Registry aprobados. Una batería ampliada de159 casos terminó con un fallo de Virilidad3229 y un error del extractor de orientación (`generation` ausente); no es un gate verde ni cubre aún el manifiesto completo solicitado. Se investigan ambos y se conserva separada la evidencia de fuente y de imagen.

Causa concreta de Virilidad acreditada con traza local: raíz149539 se registra a nivel20 y recibe activación1003; el replay conserva la suscripción pero pierde el contenedor nativo de hechizo al reconstruir la invocación. El hijo149541 recibe nivel0 y su mínimo1 lo descarta. Corrección de esta frontera en preparación para revisión, sin eliminar el mínimo ni cambiar las reglas de la pasiva.

Imagen de la corrección de checkpoint: `wakemu-shared-checkpoint-candidate:20261007`, SHA `3e4f96d770e0a023dd107f201bdca69fc494908d77c151b69ff164a9f8de63ac`. La aplicación cambia solamente dispatcher, Registry compartido y almacenamiento de checkpoint respecto de afad; el arreglo de contenedor de pasivas se prepara aparte y todavía no forma parte de esa imagen. Manifiesto de30 módulos y runners TLS preparado; no ejecutado por presión de recursos del VM de Docker. Se solicitó detener únicamente la candidata aislada para liberar recursos; no se reinició live ni el benchmark de IA. Health local agotó3s, por lo que la salud actual queda por revalidar.

La orden de stop terminó con respuesta del daemon: la candidata aislada `3ef67c475e52` ya era un proceso zombie y Docker no pudo matarla. Esto sí acredita que esa instancia no sirve como runner activo; se conservaron sus logs. No se confunde con un timeout ni se afirma que el stop haya liberado recursos.

Corrección de contenedor de pasivas en fuente: gate independiente38/38 aprobado en transmisión de nivel, grupos retenidos, replay de eventos e inicialización real de servidor (incluida Virilidad3229). Falta probar la reconstrucción activa desde checkpoint antiguo/nuevo y construir una imagen que incluya esta frontera. La imagen3e4f no contiene estos cambios; sus249 casos posteriores no se dan por verdes: error de ruta de catálogo territorial y test nuevo que exige el campo todavía ausente en la imagen.

## Resultado manual — 7 de octubre, imagen1ed06

Rechazo de invitación confirmado; el desafiante no muestra modal de cancelar. El duelo18 falló al atacar por `Missing authoritative native actor direction`. Logs muestran Ready con `Runtime belongs to another fight`, dos expiraciones cercanas desde los sockets propietarios, ACKs rechazados y abandono13952 rechazado como `Unsupported or foreign abandon participant`. Al salir ambos desapareció visualmente el combate, pero otro combate PvE fue rechazado como `Fight/actor already registered`. SQL marcaba duelo18 abortado; reiniciar world con la misma imagen limpió memoria y se verificó Docker healthy y HTTPhealth OK. Esto recupera el servicio, no soluciona la causa. Correcciones de dirección, Ready/runtime, expiración compartida, abandono y limpieza en curso; no repetir la aceptación hasta validar y desplegar.

## Correcciones después de la prueba manual — fuente no desplegada

Dirección autoritativa incorporada al FSM y preservada en checkpoints: bootstrap/serializadores coinciden para jugadores, NPCs y summons; gate local40/40 incluye ataques ordinarios en ambos sentidos y snapshots de direcciones modificadas. Ready conserva la identidad de la Fight candidata y su RuntimeMessages. El vencimiento compartido se serializa bajo lock, conserva la barrera ACK pendiente y valida la siguiente barrera antes de publicar estado. Abandono13952 en duelos usa forfeit y settlement común; regresiones verifican liberación del registro tras ambos retornos. Suites conjuntas `test_friendly_duels test_combat_shared`:49/49 aprobadas con checkout montado y PostgreSQL aislado, incluida Ready→checkpoint. Gate de imagen y TLS real13260/13952/vencimiento/PvE posterior pendientes; estas pruebas de fuente no sustituyen la aceptación visual. Modal de cancelar del iniciador todavía sin contrato nativo demostrado.

## Modal del iniciador: contrato nativo cotejado

`cWb` acción8/`cWi.run` envía12117 y muestra el aviso local `fight.invitation`; no crea diálogo/estado de espera ni una solicitud de cancelación para el iniciador. El registro nativo de handlers (`native-cle-13852.txt`) mapea solo12708→`ckQ` y13179→`ckR` para esta invitación: `ckQ` presenta errores; `ckR.a(cve)` crea `fight.invitation.dialog` solo en el receptor y su callback produce13520. La aceptación no tiene ACK independiente y continúa por el bootstrap normal del combate. `12708` causa4 es una notificación servidor→cliente, no un ACK ni una solicitud de cancelación. No hay opcode de cancelación del iniciador en el flujo nativo cotejado; no se inventa uno ni se modifica UI. El modal “esperando/cancelar” no forma parte de esta implementación nativa. La cuarentena local de respuestas repetidas same-direction sigue siendo necesaria mientras13520 carezca de nonce; la invitación inversa debe permanecer desbloqueada.

## Gate integrado congelado r2

Imagen `6111a6d4d6d913fb4f06a24b3aa3617e34ce69a13d4a9bda8378c31ee671107f`:337/337 pruebas aprobadas, cero errores/fallos/omisiones,187.261s. Runner comprueba DSN candidata aislada, secret no vacío y conexión SQL; aplicación congelada y tests con manifiesto, captura oficial de replay `snapshot-final/decoded/frames.jsonl`. Artefacto `.runtime/local/duel-core-final-context-20261007/app-only-gate-20261007-r2-final.txt`. Corridas anteriores se conservan como fallidas por configuración/fixtures y no se cuentan como aprobadas. TLS del duelo real pendiente. No desplegado; fix de anclaje del marcador16 requiere overlay adicional.

## Fallo de integración detectado por TLS

El primer duelo por protocolo cerró la sesión después de rendirse en colocación: el loop llamaba `CombatSessionAdapter.expire_current_turn`, pero solo Registry tenía ese método. El resultado durable se guardó; faltó procesar retorno12925 por el AttributeError. Se añadió delegación en el adaptador con una regresión dirigida aprobada. Comprobación adicional de todas las llamadas directas de `COMBAT_SESSIONS` en el dispatcher:17 métodos, ninguno ausente en la clase de fuente. Esta comprobación no sustituye la repetición TLS en la imagen corregida.

## Fallo real de retorno detectado en TLS r5

El resultado de derrota termina el duelo sin premios, pero recibir13974 no acredita que12925 complete el retorno. Los logs de los combates9/11 muestran `combat_return_rejected: Expected a unique owned group roster`: la rama común intenta ejecutar `dead_world_removals` con roster NPC vacío para un duelo, después de enviar paquetes de retorno y antes de limpiar el Registry y las referencias locales. Debe omitir esa limpieza exclusivamente para duelos, preservando las validaciones de PvE. También se revisa la readopción de propietarios ya retornados. La candidata r5 no se despliega; hace falta regresión y TLS de PvE posterior con la misma sesión.

## TLS de acciones y retorno en r6

Imagen2f909f67: gate61/61 sin omisiones. Artefacto `.runtime/local/duel-core-final-context-20261007-r6/action-tls-smoke-rerun3.txt` acredita abandono13952 en colocación(combate8), ataques13260 desde ambos propietarios15/16, vencimiento y ACK de ambos, abandono activo(combate9), retornos12925 y PvE posterior en la misma sesión(combate10). Los logs muestran retornos completados y !mob autorizado; el bloqueo residual está corregido. Quedó un error de checkpoint del segundo propietario: el Registry se retira antes del guardado terminal. Corrección de orden y candidata posterior en validación; r6 no se despliega todavía.

## Gate r7 recuperado

El primer runner terminó sin resultado completo durante presión de recursos y no se considera aprobado. Tras comprobar proceso y contenedor ausentes, se repitió la misma selección en la imagen da4c703b:62/62 aprobadas,0 fallos,0 errores,0 omisiones,en89,515s. Artefacto `.runtime/local/duel-core-final-context-20261007-r7/targeted-app-gate-r7-recovery.txt`. TLS posterior y revisión de logs de checkpoint pendientes.
