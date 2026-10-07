# 16. No se pueden ver los combates

Mostrar combates vivos y permitir observación sin autoridad para actuar.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**Estado vigente: 🔍 En revision.** r14 (`3af10843`) instalada, healthy y117 pruebas integradas aprobadas. r12/r13 fueron rechazadas visualmente por el usuario. La reproducción con consumidor Java real identificó la asociación incorrecta: mys llevaba casillas en vez de particiones18×18; con el emisor corregido cdE.l cambia de false a true. Verificación visual propia en curso con dos cuentas/perfiles de prueba; no pedir otra repetición al usuario hasta comprobar el resultado en pantalla.

Se implementaron y probaron piezas aisladas del servidor: el sobre nativo de entrada `cva/12044`, su sección de timeline `feN`, un constructor del snapshot desde el `SharedFight`, y un registro de suscripciones separado de los actores del combate. Los snapshots de acción incluyen la línea temporal actual y los carriers retained verificados, y rechazan estados sin población/orden conocida. **El recorrido todavía no está integrado**: el dispatcher no conecta `13413`/`12154`, no publica snapshots del combate vivo ni hace fanout a observadores o retorno al mundo al salir/cerrar. No se ha ejecutado una sesión TLS de espectador.

## Dependencias

14, 15, 33. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Observar nunca concede control; un cliente lento o desconectado no bloquea el combate observado.

[Salida nativa y separación de subscriptions](REVISION-RESPUESTAS.md).

La entrada comprobada es `coL/13413` con i32 `fight_id`; la salida es `cpg/12154` con el mismo layout. La respuesta de entrada es `cva/12044`: hereda el bootstrap `cvb/12847` y añade fase `fbZ` e i32-length-prefixed bytes del timeline `feN`. Un verificador contra el JAR instalado acepta el fixture producido por el encoder Python y confirma que el timeline vuelve a serializarse igual.

`combat_spectator_snapshot.current_snapshot` toma stats/efectos actorales del serializador autoritativo, topología y líderes del contexto compartido, y reconstruye `myG` desde placement o desde el timeline de recuperación actual. Comprueba la población retained completa en su orden guardado y vuelve a entregar carriers con ejecución desactivada. `combat_spectators.SpectatorRegistry` mantiene sesiones aparte, valida lease/mapa/instancia y autorización explícita, entrega el último snapshot al entrar y solo encola eventos posteriores. Los observadores nunca se agregan a `Fight.actors`, participantes compartidos ni settlement. Estas piezas aún necesitan el cableado del dispatcher, el ciclo de marcador 13753 y la restauración del mundo.

## Integración de marcadores públicos — 7 de octubre

Fuente congelada: creación13753 en colocación, actualización a ACTION y retirada12238 al finalizar. Solo PvE en instancia pública0; no anuncia duelos ni arenas privadas. UID de marcador asignado por política local `2**62 + fight_id`, con límites int64; líderes/equipos y coordenadas capturadas del mundo. La instancia wire de la arena no se confunde con el scope público. Participantes y espectadores ya dentro quedan excluidos de la difusión mundial. Reentrada y salida12154 recuperan el marcador vigente y snapshots del mundo. Gate enfocado60/60 aprobado por el agente; verificación independiente local de módulos de marcadores7/7 aprobada. TLS integrado aún pendiente y servidor activo sin este cambio.

## Hallazgos del TLS integrado

La candidata1bc mostró que el snapshot confundía la instancia wire de la arena con la instancia del mundo. Se corrigió esa validación preservando el rechazo de mapas ajenos y scopes inválidos; gate local25/25 aprobado con dos regresiones nuevas. El cambio aún requiere nueva imagen. El periodo activo de espera de ACK tampoco tiene deadline por diseño: la siguiente cuenta atrás solo empieza cuando todos confirman. Se prepara entrada de espectador pendiente y cancelable durante ese intervalo; no se fabrica un plazo ni se marca este TLS como aprobado.

Entrada pendiente implementada en fuente: conserva el flujo público para observadores actuales durante ACK, materializa nuevas solicitudes solo tras snapshot fresco, limita la cola y cancela por salida/desconexión/cambio de ubicación/sesión reemplazada/cierre. La comprobación de ubicación usa estado vigente, no solo coordenadas congeladas de la solicitud. Revisión independiente69/69 en módulos de espectadores/snapshot/eventos/marcadores/Registry/sincronización aprobada. Nueva imagen y TLS aún pendientes.

Candidata reconstruida `afad4acebaa8d69953f7fa4d882bd2e3ee4fbbc3a2899e488c1e47f40a92e2a4` (`20261007-ack-gap`) ya arranca y publica listeners. Cotejo de218 módulos frente al livee839: se mantienen los202 comunes idénticos y las mismas7 modificaciones revisadas, sin cambios adicionales de LOS/motor de efectos. El harness TLS se está ajustando para distinguir el fin de turno vigente de un12502 antiguo en su buffer; no se declara cubierto el periodo ACK hasta reproducir realmente esa rama.

TLS en candidataafad: fight8 acredita entrada inicial, salida y `combat_spectator_entry_deferred` (12:35:31.128 UTC). El runner informa bootstrap entregado después del13510 del propietario; todavía no completa el gate porque el golpe final apuntó a una celda diagonal fuera del rango legal. Se ajusta exclusivamente la colocación/objetivo del harness; no se relaja rango ni LOS del servidor. No declarar TLS integral PASS por esta evidencia parcial.

Los lectores TLS de los harnesses se corrigieron para conservar bytes parciales tras timeout; fragmento→timeout→resto y EOF parcial tienen2/2 regresiones aprobadas. La selección del spawn usa el grupo devuelto por la consola para evitar monstruos de pruebas anteriores. Son correcciones del harness, no cambios de rango/LOS/protocolo del servidor. El gate completo aún debe terminar.

## TLS completo de tres clientes aprobado

Imagenafad, fight13: markers placement/ACTION/restauración tras12154, snapshot actual12044, entrada diferida durante ACK, observador previo recibe12502, timeline posterior round1/turn2 con deadline futuro≈29s y sin replay histórico. Ambos observadores reciben13509/12238; SQL confirma premio solo para propietario y ningún observador como participante. Sockets continúan activos tras el cierre. Artefacto privado `.runtime/local/duel-ackgap-spectator-tls-smoke-20261007.txt`, runner09710613…aa20d. Gate final PostgreSQL y regresiones generales aún pendientes; no desplegado ni confirmado visualmente.

## Resultado manual — 7 de octubre

El observador no ve espadas mientras Adael está en colocación PvE, por lo que no puede entrar a observar. Logs del bootd04ab9e1 registran publicación13753 para combate20/mapa1134/instancia0 a15:11:53UTC y retirada12238 a15:12:43UTC. Esto acredita publicación del servidor, no que el cliente cree el marcador. Estado vigente: En revision; contrato visual y entrega en investigación.

La revisión de entrega identifica al observador: connection `cc1facf6719447e39820db2a13109dc7`, personaje7 `krill`, seleccionado a15:11:27UTC, recibió el13753 del combate20 a15:11:53UTC (50.938 bytes). El envío al socket correcto queda acreditado; sigue sin probar creación gráfica del marcador por el consumidor nativo.

## Verificación TLS del origen en r5

Artefacto `.runtime/local/r5-spectator-marker-smoke/result.txt`: combate12,13753 con origen público(-12,-8,-1), coincidente con mys y personaje;12044 mantiene origen privado(-63,-32,-4) e instancia25. Geometría y metadatos conservados. Las aserciones del marcador pasan; el recorrido completo se detuvo luego por esperar674 en vez del rechazo nativo12708 al desafío de un observador. Se revisa ese contrato del harness y se repite el ciclo restante. Render visual todavía pendiente; no desplegado.

## Registro de terreno del observador — 7 de octubre

La decodificación de 13753 identifica `myo` como el índice de terreno que el consumidor `ckM` pasa a `fbr.iU`; no es el id del mapa. El cliente instala `bcX` como instancia global de `fbr` al inicializar los datos del mundo. `bcX.iU(id)` consulta el registro y, si no encuentra la entrada, `iQ(id)` obtiene la plantilla `aKa` por id, crea el objeto con `bcN.a(aKa)`, registra `faV` en el mismo `fbr` y carga sus efectos. La prueba ejecutable `.runtime/local/ProbeFbrLookup.java` configura el catálogo de datos, inicializa los proveedores y llama directamente a `fbr.fTN().iU(46)`; resultado: `world_fbr_lookup=PASS class=bcF faP=true id=46`. El policy local está descrito en `server/protocol/local-pve-border-policy.json`. Por ello, el `terrain_effect_id=46` emitido en `myo` es resoluble por el registro global que consulta el observador. Esto prueba catálogo/registro/decoder, no render visual en una sesión manual.

## Diagnóstico del cierre automático del espectador

Rerun r5 combate15: entrada/salida/reentrada y rechazo nativo12708 aprobados; SQL acredita participantes y premio solo al propietario32, nunca al observador33. El recorrido falla al terminar: falta12238 terminal en el socket del observador. Bytecode nativo `ckc.a(cvF)`/`aUH.cbj()` demuestra que12238 provoca cleanup y callback12925;12154 corresponde exclusivamente a salida manual. El dispatcher actual elimina la suscripción tras drenar el batch terminal, sin conservar estado para correlacionar12925 ni restaurar el mundo propio; su handler12925 exige fight_messages y excluye espectadores. Se implementará cierre12238 y ACK12925 dedicado, validado por sesión/combate, sin incorporar al observador como participante ni conceder premios. No es suficiente probar recepción de13509: ese opcode es animación de melee.

## Causa visual de 13753 encontrada en r9

El cliente sí recibió el anuncio, pero `ckM` abortó antes de crear el actor de marcador `fbm`. En `.runtime/local/preferences/logs/wakfu.log` aparece `Impossible de créer la bulle de combat : la zone d'effet d'index 1134 n'existe pas`; el mismo error se repite en `client-console.log` para fight23. El bytecode `coverage-ckM.txt` muestra que el campo `cuY.eHc()` se pasa a `fbr.iU(long)`, que busca el `faP` de terreno/área necesario para insertar el marcador. El emisor había llenado `myo` con `shared.map_id` (1134), aunque el bootstrap nativo llena ese campo con `terrain_effect_id` (46 en la fixture de combate). Por eso corregir el origen geométrico no bastó.

La fuente ahora exige el `terrain_effect_id` autoritativo y lo escribe en `myo`; la regresión verifica que no se reutilice el ID público del mapa y que falte el campo para fallar de forma cerrada. Las suites de marcador, dispatch e IDs pasan 11/11. Este arreglo todavía no está desplegado ni verificado visualmente en cliente: la prueba pendiente es reiniciar/reconectar con el cambio, confirmar que `ckM` ya no registra ese error, ver las espadas en la pelea Mimic y probar observar/unirse.

## Corrección del cierre en fuente

Se añade terminal12238 normal y estado TerminalAck ligado al observador para validar12925 antes de restaurar el mundo propio. El fallback genera su prefijo sobre una copia del runtime y preserva el contador autoritativo. Verificación local: `PYTHONPATH=server .runtime/local/verification-venv/bin/python -m unittest server.tests.test_combat_results server.tests.test_combat_spectators server.tests.test_combat_spectator_events server.tests.test_combat_spectator_return_dispatch`:32/32 aprobadas. Falta congelar imagen y verificar el cierre con conexiones reales; no desplegado.

## TLS r8: importación incompatible detectada

Imagen271f1d97:106/106 pruebas enfocadas aprobadas, pero el TLS real falló al cerrar por `No module named wakfu_server.combat.wire`: el import anidado de combat_results no comparte la ruta plana usada por el servidor. Los imports de resultados, eventos y TerminalAck se normalizan a wakfu_server.combat_results/combat_spectator_events/combat_spectators para evitar también clases ObserverSession duplicadas.32 pruebas enfocadas en fuente siguen aprobadas. Nueva candidata r9 en preparación; r8 no se despliega. Artefacto `.runtime/local/spectator-terminal-context-r8-20261007/spectator-terminal-tls-output.txt`.

## Candidata r9 construida

Imagen1c3bbea5 incluye únicamente las importaciones planas corregidas sobre r8. Gate de32 pruebas enfocadas dentro de la imagen aprobado en0,739s; importaciones reales de combat_results, combat_spectators y combat_spectator_events comprobadas en el contenedor. Arranque aislado en curso; TLS completo pendiente. Sin cambios al servidor activo.

## TLS completo del cierre en r9 aprobado

Imagen1c3bbea5, combate2: marcador público(-12,-8,-1), arena12044 privada(-63,-32,-4), entrada/salida/reentrada, eventos12502/13509, cierre12238 normal y callback12925 del observador con flag1. Recibió snapshot13984 al retornar. Log17:17:33UTC acredita combat_spectator_terminal_returned, native_return_ack=true, world_refreshed=true. SQL confirma premio solo al propietario y observador ausente de participantes/recompensas. Artefactos `.runtime/local/spectator-terminal-context-r9-20261007/spectator-terminal-tls-output.txt` y `spectator-return-log-review.json`. Falta TLS de duelos en la misma imagen, promoción y aceptación visual.


## Regresión visual r9 — causa concreta

El usuario confirma que en PvE con Wayo/Krozz no aparecen espadas ni acceso de observar/unirse. El log del cliente rechaza13753 del fight23: «Impossible de créer la bulle de combat : la zone d’effet d’index1134 n’existe pas». El emitter usa `myo=shared.map_id`; el consumidor `ckM` usa ese campo para buscar una zona registrada en `fbr`, no un mapa. El origen público corregido no basta. Estado **En revision**: cotejar el identificador/registro nativo y añadir regresión antes de otra aceptación visual. Los smokes TLS previos no prueban creación de sprite.

## Evidencia visual r12

Usuario confirma que las espadas siguen ausentes: Wayo en colocación contra Mimic y Krozz en exploración. Captura TLS de Krozz `2026-10-07T18-53-29.047470Z-f63d6909` recibe 13753 para fights 26/27: myo=46, kind=2, fase de colocación/activo, celdas (-24,17)/(-23,17). No hay nuevos errores `ckM` de índice 1134 después de las 13:00:18 hora local del cliente; este error sí aparece en intentos anteriores.

La hipótesis de `instance_id=10` era incompleta: aunque `ckM` recibe la topología y crea los modelos, r13 siguió sin mostrar las espadas. No se debe atribuir la ausencia de sprites únicamente a la instancia QI.

## Corrección r13

Imagen4b1bf709 hereda r12 y modifica únicamente combat_external_markers: QI instance_id0. Gate116/116 integrado aprobado. No se promueve la retirada multiowner en desarrollo. La prueba visual posterior de usuario falló.

Usuario rechaza r13 con dos capturas: combate contra2Wonejos, personaje externo sin espadas. Cambiar QIinstance0 tampoco resolvió render. No pedir nuevas repeticiones de hipótesis sin verificación visual propia.

## Diagnóstico nativo posterior a r13: `mys` requiere particiones

La captura r13 de fight32 (2026-10-07T19:20:59.654006Z) recibió 13753 con QI en la celda pública `(-22,16)`, `mys=[(-22,16)]`, `myo=46` y `kind=2`. El consumidor instalado no interpreta `mys` como world cells: `cdE.l(buG)` entrega cada par directamente a `Vc.aD(x,y)`, que busca la partición `cdz` con coordenadas iguales. `Vc.aC(worldX,worldY)` crea esa rejilla usando `Ve.qb/qc`; ambos calculan `GS.B(world/18)`, es decir floor-división entre18 incluso para negativos. `cdz.aQc()` vuelve a comparar `mys` contra el `bbn/bbo` de la partición para registrar el encuentro. Para la celda capturada, la clave nativa es `(-2,0)`. Con el par crudo `(-22,16)`, `cdE.l` devuelve false y no asocia el `buG` a ninguna partición; con `(-2,0)` devuelve true.

Se corrigió el emisor para conservar QI en la celda del mundo y codificar `mys` como las claves de partición nativas. La regresión Java privada `ProbeR13NativePartition` usa `cuY.dp` sobre el cuerpo 13753 capturado y las clases reales `cdE`/`Vc`/`cdz`: la captura antigua produjo `captured_mys_registered=false`, mientras que el paquete generado por el emisor corregido produjo `captured_mys_registered=true`. Evidencia reproducible en `.runtime/local/ProbeR13NativePartition.java`, `.runtime/local/r13-marker-13753.bin` y `.runtime/local/r13-marker-fixed-13753.bin`. Suite Python: `PYTHONPATH=server python3 -m unittest server.tests.test_combat_external_markers -v`, 7/7. Esto acredita parser y asociación a partición nativa, pero no el render visual final; `screencapture` no pudo obtener una imagen y no había sesión GUI activa. La nueva candidata aún requiere validación con captura visual antes de afirmar que el usuario ve las espadas.

## Reproducción propia visual r14

Dos cuentas de prueba propias entraron al mapa1134. Observador recibió13753 de fight33 en colocación/activo con mys(-1,-1), myo46 y QIinstancia0. Captura propia `issue16-marker-visual-observer/fight33-observer-after.png` confirma que no aparecen las espadas. La asociación de partición corregida no basta para renderizar. El error cdE de resource[-15,18] ocurrió42s antes del marcador y no se atribuye al combate. Investigar registro de líderes/sprite y semántica de actualizaciones; no pedir otra prueba al usuario.
