# Armadura1013: aplicación y presentación cliente

Caso real: pelea12026320, actor11, Pie de Roca5033. El checkpoint SQLite contiene ARMOR97=7 y HP276. No se declara resuelta la presentación GUI.

El cliente usa ARMOR97: `bkr.ay` construye `bkl` sobre `big.e(ffw.shQ)`; `bkN.eH` consulta la misma característica. No es VIRTUAL_HP92 ni un campo alternativo de armadura.

Tres pruebas originales offline descartan una pérdida de valor en los encoders comunes examinados:

- `ProbeNativeArmorClient.java`: paquete13497 generado por NativeArmorHandler → `cvY.dp` → registro1013/eWx → `ds` → aplicación original `eWW.c`, ARMOR0→7; retirada original `eWQ.fNM`, ARMOR7→0. Conserva UID y AdditionalDatas.
- `ProbeNativeArmorRefresh.java`: `snapshot_characteristics` generado desde el checkpoint real → `tA.aG` → `ffh.b`. Conserva la instancia original `fff`, ARMOR0→7 y notifica al observador `PD` con7.
- `ProbeNativeArmorActorRefresh.java`: paquete completo12873 generado con `actual_actor_stats` desde ese checkpoint → `cuU.dp` → descriptor PC original `eHk.ew`. Ambas secciones nativas de características contienen ARMOR7.

Los archivos binarios generados quedan privados en `.runtime/local/armor-*.bin`. El descriptor PC concreto importa: la base abstracta eHd tiene secciones vacías y no sustituye al decoder eHk.

El handler real12873 es `cjU`: encola el refresh, obtiene el actor del combate y llama `big.a(blob,false)`. El13497/cjL encola la acción aTR y registra el running effect; comprobar sólo13497 no demuestra que el HUD haya ejecutado la actualización posterior.

Resultado: no se encontró una discrepancia de codec que justifique un parche arbitrario. Falta capturar el12873 efectivamente entregado y observar el getter ARMOR de la instancia cliente al ejecutar la cola, para distinguir entrega/orden, actor seleccionado y presentación visual. Estas pruebas son offline y no son una validación GUI.

## Comprobación GUI real del perfil aislado

El4oct2026 se lanzó exclusivamente `agent-spell-test`/actor11, sin Dada y sin reiniciar world. Pelea960375838, nivel20. Un clic normal de Pie de Roca produjo request `89fc6b5525f04b3586fae159bade42fc` a18:03:28UTC. El inspector leyó la instancia real `fight.rj(11).c(ffw.shQ)`: antes0, después7; HP410.

La captura de entrada contiene12873 frame528, seq2248,18:03:28.441373UTC. El cuerpo **recibido**, sin reconstrucción, pasa el decoder original `cuU.dp/eHk.ew`, con ARMOR7 en ambas secciones. La captura de pantalla muestra una barra gris sobre la barra azul del actor. El corazón central muestra los PDV; no se inventó una modificación cliente para añadir allí una cifra de armadura.

Absorción sigue pendiente: los NPC de esta pelea carecen de ataque auditado y no sirven como prueba. Un autosacrificio5031 legítimo posterior dejó ARMOR7 y HP370; tampoco demuestra absorción de un ataque enemigo. Se necesita una pelea aislada con atacante conocido, por ejemplo Wonejo3646nivel1. Informe: `docs/reports/combat-inventory/pie-de-roca-5033-client-delivery.json`. Capturas y binarios completos permanecen privados en `.runtime`. Cliente aislado cerrado al terminar; no se tocó el cliente principal ni servicios.


### Segunda prueba GUI: defecto de absorción de la IA (2026-10-04)

En el perfil aislado `agent-spell-test`, actor11, combate453142470, los
NPC semillas5525/nivel1 ejecutaron Golpe de Wonejo real. Pie de Roca se
lanzó mediante el atajo5 y el cliente mostró la barra de armadura y ARMOR97=7.
A las18:31:21 UTC el cliente tenía HP385/ARMOR7; tras otro ataque, a las
18:31:35, HP380/ARMOR7. Por tanto la presentación estaba correcta pero la
absorción de ese productor de daño estaba defectuosa.

`combat_npc_attack.execute` usaba `Fight.apply_damage` directamente. Se ha
sustituido por el dispatcher/factoría y `NativeDamageHandler` comunes, con
la definición original7962/361119 exportada por `ExportSpellEffectTrees`.
Así se usan las estadísticas vivas, resistencia, orientación, absorciones,
UID y eventos originales. La caja de salida y el combate quedan privados
hasta terminar; no se calcula daño a partir de la variación de HP.

Seis pruebas pasan: ataque sin armadura, agotamiento de7→2 sin perder vida,
agotamiento de2→0 con3 de pérdida de vida, costes preservados, paquete del
snapshot con ARMOR2 y rollback ante fallo tardío de animación. La prueba GUI
posterior al despliegue sigue pendiente; no afirmar absorción visible resuelta.
El camino antiguo de Puño básico también usa `apply_damage` y queda pendiente
de migración separada.

Reproducción del catálogo mínimo auditado:

```sh
printf '7962\n' > .runtime/local/npc-spell-references.txt
java -cp 'client/lib/*:.runtime/java' ExportSpellEffectTrees .runtime/local/npc-spell-references.txt .runtime/local/npc-spell
python3 server/tools/convert_spell_effect_trees.py .runtime/local/npc-spell server/protocol/native-npc-spell-effect-trees.json
PYTHONPATH=server:server/tests python3 -m unittest test_combat_npc_attack -q
```

Sólo se conserva la propiedad nativa ya auditada de Wonejo5525; no se
afirman ataques operativos para todos los NPC del catálogo.


### Absorción verificada después del despliegue

Boot `a1e61197c30f43c982fa8251c372480a`, combate139371224 del perfil
aislado `agent-spell-test` (actor11): a las19:01:40 UTC el cliente mostraba
HP405/ARMOR7. Los paquetes **recibidos**12613 del daño361119, frames656
y679, UID51/55, contenían valor5 y AdditionalDatas.armadura5/2. Tras ellos,
el inspector del actor real mostró HP402/ARMOR0. Esto acredita7 absorbidos
y3 de daño restante. La prueba fue GUI manual, no el nuevo harness automático.
Las solicitudes ajenas posteriores se separan de esta secuencia temporal.

## Atracción y harness de cliente (2026-10-04)

La solicitud GUI 5030, frame2030, fight547435580/action339, boot1a3b6e1068fd4872ae8351005b17bb2a produjo el tirón esperado: NPC(-12,-6,-1)→(-12,-7,-1) hacia caster(-12,-8,-1), PA6→5 y WP6→5. La entrega IN está correlacionada con actor, pelea, acción y request_id. El harness conservó TIMEOUT_EXECUTION porque observó el resultado a2.018s con umbral2s, aunque el servidor terminó en799.761ms. Esto acredita movimiento y costes, no cumplimiento del límite de latencia. Reporte: attraction-5030-client-harness.json.

El harness lee capturas incrementalmente, limita cada consulta al deadline restante y guarda reporte parcial incluso cuando falta cliente o falla la observación. Requiere expectativas concretas, petición única exacta y entrega correlacionada; solicitudes ajenas invalidan el caso. El tiempo del primer delta se congela en los timestamps de lectura del estado cliente, sin sumar procesamiento posterior. Los fallos de configuración/fixture no se presentan como fallos del hechizo.

## Puño2145: RNG reproducible y atomicidad

Puño usa wrapper158454→daño3597 y contenedor de ítem12/2145 dentro de la misma factoría. El coste sigue siendo3PA; el valor se calcula con snapshots vivos, resistencia, localización, armadura y eventos. No se obtiene de HP ni de una función identity.

La fixture original tiene localización SIDE: daño base3 se multiplica por1,1 y UP.bt redondea3,3 a3 o4 según el RNG. Por tanto armadura7 puede quedar en4 o3; esperar siempre4 era una prueba incorrecta. `execute_unarmed(..., rng=None)` conserva azar en producción; un RNG externo reversible permite repetir las dos ramas con Random(0)/Random(1). La expectativa se calcula con la aritmética común y no fuerza la muestra a0. El decorador transaccional restaura ese RNG si falla un codec después del cálculo, junto con PA, HP, armadura, UID y eventos del preview.

Los argumentos heredados de bonus/effect lists no sustituyen snapshots. El caller actual entrega aliases vacíos y una política normal explícita; el motor sigue leyendo los bonos y estados reales. Claims no vacíos de esos formatos y una probabilidad crítica sin rama resuelta siguen rechazados, porque no existe un contrato para reconciliarlos con los snapshots ni se acreditó un roll crítico del servidor.

### Presupuestos del harness cliente (4 de octubre, 21:33 UTC)

La clasificación anterior mezclaba el tiempo de observación del cliente con el cálculo del servidor. Los resultados históricos se conservan: Puño tuvo cálculo de223,136ms y recepción del efecto aproximadamente123ms tras la solicitud; el primer snapshot con el cambio se observó después de2s. Esto no prueba que una animación haya causado la demora. El harness ahora separa `server_execution_seconds`, `request_to_wire_update_seconds`, `request_to_client_observation_seconds` y las duraciones de llamadas al inspector. `TIMEOUT_EXECUTION` corresponde al límite de cálculo2s o a ausencia de finalización; `CLIENT_OBSERVATION_TIMEOUT` corresponde a su presupuesto independiente configurable (6s por defecto). Ninguna clasificación permite PASS sin cambio exacto y entrega correlacionada.

La correlación de Puño acepta los registros `combat_melee_delivery` nuevos únicamente con requestID, boot, actor, UID del ítem y coordenadas coincidentes. Los actionID pueden diferir entre la animación13509 y el efecto12613 porque la ruta envía prefijos separados. Este soporte requiere el despliegue de esos registros; no se sustituye por cualquier paquete recibido. Validación:18 pruebas del harness y py_compile pasan. La nueva clasificación todavía no constituye una nueva prueba GUI de crítico ni de latencia.

### Ciclo GUI real en boot6ecf425a (4 de octubre, 22:22 UTC)

Puño pasó el harness estricto: pelea292704298/action30, HP del Wonejo84→80 y PA6→3, animación13509 y efecto12613 con actionID común. Cálculo158,062ms, llegada del efecto65,272ms y observación cliente1,375763s. Reporte `docs/reports/combat-inventory/unarmed-client-common-action-harness.json`.

El ciclo73484938 verificó colocación→Listo→ACTION→Puño→pasar turno (propio→NPC→propio)→lanzamientos normales hasta HP del NPC0→panel Victoria→mundo→nuevo combate619232779→Listo→ACTION. No se acreditó rendición: «Abandonar» en el menúESC pide salir de WAKFU. Nueve decisiones críticas automáticas tuvieron chance3 y rolls superiores a3; ninguna muestra crítica. Evidencias `combat-cycle-client-evidence.json`, `combat-cycle-turn.json` y `combat-cycle-finish-attempt.json`.

Atracción pasó en el combate reiniciado619232779/action31: NPC(−20,2,−1)→(−19,2,0), PA−1 y PW−1. Cálculo141,079ms, efecto recibido37,277ms y observación cliente1,332718s. Reporte `attraction-5030-client-cycle.json`. Los intentos previos permanecen negativos: objetivo obsoleto o movimiento hacia(−17,4,0), celda inexistente en la geometría nativa1134. Esos fallos de fixture no acreditan un bloqueo del motor.

El harness acepta `target_actor_id`: verifica identidad, vida y celda antes de seleccionar y antes del click, además del turno propioACTION. Un cambio invalida el caso como `INVALIDATED_PRECONDITION`; sin solicitud con precondiciones estables sigue `BLOCKED_CLIENT`. Veintiuna pruebas focales pasan. La política de muestra crítica natural exige expectativas explícitas para ambas ramas, compara la rama real con la decisión del servidor y etiqueta una muestra válida como normal o crítica; obtener un resultado normal por azar no constituye fallo del motor.
