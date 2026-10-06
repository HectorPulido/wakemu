# E06 — comando de nivel atómico (avance parcial)

`!nivel` antes confirmaba nivel/XP y después inicializaba salud y generaba el snapshot en otro paso. Ahora nivel, XP, salud y baseline de regeneración se actualizan dentro de la misma transacción; el paquete también se construye antes del commit, de modo que errores de serialización/validación hacen rollback completo.

`health_store.initialize` puede recibir una conexión prestada únicamente con transacción activa. No inicia ni confirma otra transacción en ese caso; sus callers normales conservan la transacción propia.

Regresión: fallo inyectado al generar snapshot tras pedir nivel50; nivel, XP, HP, máximo y builds permanecen iguales. Suite de consola/salud:19 pruebas PASS. Se actualizó la expectativa de paquetes de equipamiento del test de consola para incluir los registros añadidos por E10.

Pendiente: normalización semántica de hojas fijas/moduladas al subir nivel, camino de recompensas de combate y actualización del roster/cliente. No se declara resuelto E06 ni subida de nivel completa.

## Reproducción específica49→50

Guardada hoja con metadata/aptitudes de nivel fijo49 y solicitado `!nivel50`. Se ejecutó con SQL y con overlay BuildJournal/MemoryRedis: la validación rechaza la hoja incompatible y la transacción conserva nivel49, XP, HP, máximo y builds anteriores. Suite consola/salud/aptitudes:17 pruebas PASS.

Esto acredita la corrección de confirmación parcial; **no** acredita subir exitosamente de nivel con esa hoja. Sigue pendiente distinguir hoja del nivel real frente a modulación y actualizarla mediante un contrato autoritativo. Las rutas del chat y API delegan al mismo `test_console.execute`; no se encontró una segunda implementación de `!nivel` en el dispatcher.

## Semántica de nivel resuelta en el cliente nativo

`eQT.al(eGj)` devuelve `eGj.drm()` únicamente cuando el nivel almacenado es-1; para cualquier nivel positivo devuelve ese valor sin consultar al personaje. Probe Java: **PASS fixed49 stays49; real-level sentinel=-1**. Por ello no convertir hojas positivas a-1 al subir nivel.

Se implementó `builds.effective_sheet_level`: hoja virtual o sentinel-1 usa nivel real; hoja fija conserva su nivel y rechaza valores superiores al real. Regresión con personaje50: hoja49 resuelve49, sentinel resuelve50, hoja51 rechaza. Suite de capacidad/codecs:12 pruebas PASS.

El resolver aún no sustituye las validaciones/evaluaciones del runtime; deben integrarse conjuntamente presupuestos, elegibilidad de equipo y salud antes de aceptar la modulación completa. Esta evidencia resuelve la duda semántica anterior, no todo el issue.

## Integración de nivel efectivo

La validación de metadata permite hoja fija entre1 y nivel real; equipo, aptitudes y validación del deck existente reciben el nivel de esa hoja. No se modificó el motor de hechizos. Cálculo de bonificaciones/salud y Store exponen el nivel efectivo seleccionado conservando `level` como nivel real.

Regresión49→50 actualizada al resultado correcto: comando exitoso, personaje50, efectivo49, mismos HP/máximo/builds y XP actualizado. Se ejecutó con SQL y overlay MemoryRedis. El ensayo anterior de rechazo documentado arriba queda superado por esta integración; la prueba separada de fallo de snapshot sigue comprobando rollback.

Suite62 casos: **48 PASS y14 SKIP** sin Redis real configurado. Se completó metadata faltante en una fixture sintética de aptitudes; no se añadió fallback para hojas persistidas inválidas.

Pendientes: verificar más consumidores/elegibilidad, estadísticas de combate y flujo de recompensas, Redis real, cliente y notificaciones de nivel/modulación. No desplegado todavía. E06 continúa parcial.

## Verificación adicional de combate

Suite `test_combat_actor`, `test_combat_actor_snapshot`, `test_combat_equipment_return`, `test_combat_health`, `test_ring_build_integration` y `test_breed_resources`: **23 pruebas PASS**. Se completó metadata de nivel real en fixtures de snapshots y recursos. La expectativa de retorno de combate se corrigió a cuatro PM para la clase8, según su catálogo nativo; no se modificó el cálculo de recursos para hacer pasar la prueba.

Esta suite comprueba regresiones de snapshots, heridas y equipo; todavía no demuestra modulación completa en combate ni recompensas de nivel.

## Persistencia comprobada con Redis aislado

Dentro del contenedor world, usando un Redis temporal sin puertos publicados y separado del Redis del juego: suites de capacidad, builds, journal, integración de anillos y Store, **61 PASS y1 SKIP** (inyección de fallo exclusiva de MemoryRedis). Incluyen selección persistida, índices dispersos, HP conservados al activar hojas y eliminación durante el checkpoint. El Redis temporal se eliminó al terminar.

Además, consola, capacidad y retorno de equipo: **22 PASS dentro de Docker**. Configurar una URL Redis en esta segunda suite no convierte sus fixtures SQL/MemoryRedis en Redis real: acredita ejecución en Docker, no una nueva reproducción de `!nivel` con Redis real. Sigue pendiente ese recorrido específico, así como cliente y recompensas. El proceso del servidor de juego no se reinició ni se declara actualizado por estas pruebas.

## Recorrido49→50 con journal pendiente y Redis real

Nueva regresión `test_level_command_with_pending_fixed_sheet_reconnect_and_checkpoint`: subir a49, guardar hoja fija49 únicamente en el journal, ejecutar `!nivel50`, reabrir Store conectado al mismo journal y finalmente hacer checkpoint y reabrir desde SQL. En las tres lecturas se conserva nivel real50/efectivo49, XP, HP, máximo y hojas. Se exige aumento de XP y se verifica que la hoja no estaba previamente en SQL. **PASS con MemoryRedis y PASS con Redis real aislado dentro de Docker**. Esta prueba completa el recorrido Redis específico pendiente en la sección anterior; siguen pendientes recompensas y cliente.

## Atomicidad de nivel por recompensa

`combat_rewards.award` confirmaba nivel, XP, wallet y recibo antes de reparar el máximo de salud. Ahora, cuando cambia el nivel, ejecuta `health_store.initialize` con la misma conexión y transacción. Una excepción revierte también XP, nivel, wallet y recibo; no queda una recompensa parcialmente confirmada.

Regresiones: fallo inyectado de salud conserva todos los valores y no genera recibo; victoria con personaje herido conserva20 HP, actualiza máximo al nivel3, persiste al reabrir y no cura ni duplica al repetir la recompensa. Suites recompensas/lifecycle/salud: **13 PASS**. No cambia fórmula ni fuentes de loot. Pendientes: hojas moduladas en esta ruta, serialización posterior al commit y cliente; implementación todavía no recargada en el proceso world.

## Recompensa con hoja fija seleccionada

`test_reward_level_preserves_selected_fixed_sheet_and_checkpoint`: personaje49 herido, hoja1 fija49 guardada en journal y activada; victoria concede exactamente la XP necesaria para50. Resultado real50/efectivo49/selección1, HP20 y mismo máximo/equipo/aptitudes. Tras checkpoint y reapertura SQL se conservan todos esos valores y XP50. **PASS con MemoryRedis y Redis real aislado en Docker**. Queda verificada esta transición concreta; falta el ciclo completo con cliente y serialización posterior al commit.

## Serialización de cierre dentro de la transacción

`prepare_finish` ahora abre una transacción y presta su conexión a `award`; construye recibo, resumen y notificación XP antes del commit. Si falla el encoder o el commit, revierte la recompensa y restaura `awaiting_ack`/`pending` del runtime. Solo devuelve los paquetes después de confirmar la transacción. La API directa de `award` conserva una transacción propia cuando no recibe conexión; rechaza conexiones prestadas sin transacción activa.

Prueba de fallo del encoder después de modificar el runtime: XP, nivel, HP, máximo, wallet y builds intactos; ningún recibo; cola y ACK previos restaurados. Suites recompensas/lifecycle/resultados/muerte: **17 PASS**. Esto sustituye el pendiente de serialización anterior. No garantiza entrega de red tras commit: se mantiene el recibo idempotente, sin afirmar entrega exactamente una vez. Falta despliegue y reproducción visual del ciclo completo.

## Recarga en Docker

Suite integrada de builds, journal, consola, recompensas, lifecycle, resultados, muerte, salud, bolsas, resincronización, equipo y recursos: **85 PASS y16 SKIP** (Redis aislado no configurado en esa ejecución). Los recorridos nuevos de Redis real se verificaron separadamente como consta arriba.

Respaldo SQLite consistente verificado con quick_check: `.runtime/local/backups/before-builds-20261005T191355Z.sqlite3`, permisos0600. Reiniciado únicamente `world`, inicio19:14:16UTC; contenedor healthy, `/health`200 y `/test/sessions` anónimo401. Los fuentes montados actuales quedan cargados en el proceso. No constituye prueba visual ni cierre de E06; tampoco se hizo commit/push. Este respaldo no introduce un backend de compatibilidad.

## Consumidor pendiente identificado

`combat_bootstrap.create_placement` construye `Actor.effective_level` con `character["level"]`, aunque Store ya expone `effective_level` de la hoja seleccionada. El dispatcher llama ese constructor con el personaje sin proyectar el nivel efectivo. Deben alinearse actor, snapshot y mensajes de colocación; no basta pasar el nivel efectivo al cálculo de HP. Esta discrepancia concreta mantiene E06 parcial y requiere regresión real50/hoja49 antes de cerrar.

## Nivel del actor corregido

La colocación resuelve ahora el nivel desde la metadata de la hoja seleccionada mediante `effective_sheet_level`, sin confiar en un campo derivado potencialmente obsoleto. Prueba real50/selección1/fija49: actor efectivo49, HP20; personaje conserva nivel50 y XP50. Format3 conserva la progresión real en su campo de XP/nivel; no se sustituyó por49, lo que rompería validación de XP. Sigue pendiente acreditar la representación de modulación del cliente y el ciclo completo. Este último cambio aún no está recargado en world.

El snapshot de jugador también verifica ahora que `Actor.effective_level` coincide con la metadata de la hoja seleccionada. Antes podía aceptar un actor50 con hoja49 porque la evaluación de equipo volvía a resolver49 y no detectaba el nivel incorrecto del actor. Regresión: snapshot con actor49 conserva HP20/máximo49; mismo actor alterado a50 rechaza explícitamente. Suites bootstrap/snapshot/recursos/equipo completo: **19 PASS**. Cambios limitados a nivel de colocación y coherencia del snapshot; sin modificar ejecución de hechizos. Pendiente recarga de este último cambio y prueba visual.

La inyección de fallo de salud se reforzó para ejecutar primero las escrituras reales de `initialize` y fallar después. Verifica dentro de la transacción que el máximo ya aumentó; tras rollback, nivel, XP, HP, máximo, wallet y builds regresan al estado anterior y no existe recibo. Suites recompensas/lifecycle/capacidad: **22 PASS**. Esta prueba acredita rollback de escrituras ya ejecutadas, además del fallo previo a las escrituras.
