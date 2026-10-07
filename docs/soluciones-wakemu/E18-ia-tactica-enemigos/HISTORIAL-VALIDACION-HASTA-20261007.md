# E18 — Motor de IA táctica de enemigos

## Estado actual — 2026-10-07

Trabajo actual en SDK host: publicación directa del primer bloque de cada
snapshot completo comprimido, evitando consulta status redundante.
El receptor valida el checksum entero del objeto existente o publica
atómicamente todos los bloques; catálogo conserva su negociación previa.
Pruebas específicas24OK/18,719s: duplicado conserva mtime y hace una sola
petición block, corrupción se repara con bytes exactos, ACK final perdido
se reintenta, snapshot multibloque conserva alias/ciclos/campos futuros.
Revisión readonly de Luna sin pérdida de referencias/datos detectada.
También se añadieron checks del deadline antes/después de comprimir y
una regresión de reloj determinista:1OK/0,515s. Primer comando focalizado
usó un nombre de clase inexistente; segundo con ContextBridgeHTTPTests pasó.
Suite421 del snapshot previo a ese último check en ejecución92922;
el snapshot final422 debe validarse antes de desplegar. No cambios world.


**Última revisión verificada:** AI `ff966ee791c1`, saludable, inicio
18:09:18Z; world `1c3bbea57e40`, conserva inicio17:23:41Z. Solo AI
reiniciado; contador propio world1/3. **419 pruebas OK**,109,737s,
169 imports del motor vivo congelado, ninguno externo;85 archivosPython
del contenedor iguales porSHA al host. Suite65913 y build46349 terminal0.
Ensayo14turnos24680 terminal0:
`.runtime/local/e18-native-leaf-seeding-live-turns.json`.
Ataques2/2 individual,0/4 concurrencia2,0/8 concurrencia4; invariantes
íntegros. Tiempos individuales4,892–5,238s, concurrencia2 4,629–5,289s,
concurrencia4 3,736–5,130s. No demuestra mejora de latencia ni aceptación
concurrente; la optimización conserva datos pero es insuficiente.
Siguiente trabajo: reducir coste de snapshots/consultas completos antes de
más ajustes de scoring; ningún parche específico para el Mimic.


Diagnóstico confirmado del Mimic del combate23: HP1, **PA0**, PM3,
WP0; posición `[-23,16,-8]`, rival `[-23,17,-9]`, ya adyacentes.
Los cinco Mimics del catálogo vivo conservan `native_abilities=[]`.
Los dos movimientos del turno44 gastan2PM y mantienen la distancia1:
score−0,2 frente a0 por pasar. No se inventa un ataque ni se fuerza gastar PM.
La ausencia de hechizos y los plazos de consulta son problemas distintos.
Arquetipos de huida/distancia deberán expresar utilidad genérica mediante
capacidades/perfiles, sin identificación de especies en el algoritmo.

Optimización general de preparación fría de geometría en el SDK host:
construye primero literales de coordenadas válidas y evita templates desechados
/excepciones por aristas anidadas. **44 pruebas específicas OK**, incluye
rechazo de campos futuros/reordenados y verificación de aristas/aliases.
Comparación alternada controlada:7.075celdas,24.556aristas,31.632nodos,
2.147.041bytes idénticos SHA
`00838dbefe36a49d2b11f5591abb4bafab35584a62d3958972ca810af8aa13e0`.
Mediana preparación templates0,139s anterior vs0,128s actual; no es SLA.
Artefacto `.runtime/local/e18-geometry-leaf-seeding-controlled.json`.
Suite ampliada **419 pruebas OK**,109,737s;169 imports congelados,
ninguno externo, footerSUITE_EXIT0. Proceso65913 terminal0. Optimización desplegada en AI
**ff966ee791c1**, saludable desde18:09:18Z; world conserva imagen e inicio.
Los85 archivosPython del SDK empaquetado coinciden porSHA con el host. Log
`.runtime/local/e18-ai-leaf-seeding-full-suite.log`.

**Política exigida por el usuario:** arquetipos y capacidades genéricos;
ninguna regla táctica por nombre o ID de monstruo. Solo se admiten excepciones
para mecánicas explícitas de monstruos de tipo puzzle. El diagnóstico del
Mimic debe corregir el sistema general.

Actualización: diagnóstico de Mimic, combate **23**. Los turnos iniciales se
rechazaban con `Selected native build is absent`: la build permanente cero
no necesita una fila guardada, pero el adaptador la exigía. Corrección en
`server/ai-service/wakfu_ai/native/native_store.py`, sin cambios en world: conserva el carácter
completo y usa `catalog_indices` y `default_deck` nativos. Ocho pruebas
específicas pasan; suite ampliada de **417 pruebas OK**, 204,481 s,
169 imports del motor vivo congelado y ninguno externo
(`.runtime/local/e18-ai-default-build-full-suite.log`, proceso terminal0).
Los turnos posteriores ya superan esa carga, pero todavía muestran plazos
agotados o `end_turn`: los movimientos examinados conservan distancia
topológica 1 y puntúan por debajo de pasar. El comportamiento del Mimic
sigue pendiente; tener PM por sí solo no demuestra que la búsqueda seleccione
un desplazamiento. No se declara resuelto ni se reinicia world.
World vivo `1c3bbea57e40`; AI **`a3a18453ee29`**, saludable desde
`2026-10-07T17:58:42.101067398Z`, corrección de build cero desplegada.
World conserva imagen e inicio; no se consumió otro reinicio.
Verificación read-only dentro de world con el personaje real del combate:
`characterId=10`, build seleccionada0, filas guardadas `[]`, catálogo nativo
`[0]`, deck24bytes; `load_authorities` carga correctamente. No se mutó DB.
Ensayo actual32369 terminal0, mismo motor vivo: **2/2 ataques individuales**,
**0/4 con concurrencia2**, **0/8 con concurrencia4**; invariantes íntegros.
Artefacto `.runtime/local/e18-native-build-zero-live-turns.json`.
La aceptación concurrente sigue fallando; no se confunde con suite verde.
Perfil diagnóstico80041 del motor actual terminal0, un solo encuentro;
no usar tiempos instrumentados como SLA.

La suite anterior de **415 pruebas pasa sobre el motor vivo congelado 1c3bbe**
(log `e18-ai-fast-tuple-live-fixtures-frozen-suite.log`, 94,234 s).


**En implementación. Puente final v3 desplegado y servicios saludables; aceptación en juego pendiente.**
El puente se desplegó en `ff2659e929a2`, basado íntegramente en
`2e64d4e0730b`, cambiando solo `pass_test_monster_turn`. Otra sesión actualizó
world a `1ed06b10b4d2` (inicio `2026-10-07T14:18:11.366599745Z`);
conserva el puente genérico y el volumen read-only,
verificados el 7 de octubre. El SDK se monta
en lectura desde `server/ai-service`; la selección del contexto, decisiones
y entrega nativa permanecen allí. Reinicio propio realizado: **1/3**.

Límite explícito del usuario: **máximo tres reinicios propios de world en total**.
Avisar antes de cada reinicio. El tercero cierra también la autorización para
seguir cambiando archivos; después de ese reinicio no se realizará ningún
cambio adicional. No consumir reinicios de world para iteraciones de AI.

Observación actual: otra sesión actualizó world a `1c3bbea57e40`, saludable,
inicio `2026-10-07T17:23:41.380836015Z`. AI `be646eb063c8`, saludable,
inicio `2026-10-07T17:30:43.992436322Z`; build27661 terminal0 desde el catálogo
íntegro de la imagen viva. Reinicios propios **1/3** (ninguno adicional).
Encoder directo de tuplas exactas de enteros desplegado, bytes/IDs íntegros.

Suite47906 terminal0 sobre motor anterior1ed06: **415 pruebas OK**,118,408s;
169 imports congelados,1.405 registros before/after idénticos SHA
`c0e2bc886e5b059c92d94093a8ddce06d2ec852d1f2c5c566591844066bdb62b`.
Comparación alternada sintética50.000 tuplas:bytes idénticos, mediana0,237s
anterior vs0,111s actual; no es latencia de combate.
Ensayo88172 en curso con SDK nuevo y motor congelado anterior1ed06:
`.runtime/local/e18-native-fast-tuple-distant-turns.json` / `.log`.
Es diagnóstico del motor anterior, no aceptación del world actual1c3bbe.
Después: copia íntegra de imagen1c3bbe, suite con ese motor y ensayo14 turnos
sobre esa misma fuente. Sin editar ni reiniciar world.
Aceptación concurrente y manual integral pendientes. Progreso aproximado85%.

Última medición distante terminal (83433, motor1ed06/AIb897): ataques2/2,0/4,0/8;
movimientos2/2,3/4,2/8; invariantes intactos, aceptación concurrente no cumplida.
`.runtime/local/e18-native-range-order-distant-turns.json`.

### Evidencia histórica de revisiones anteriores

### Despliegue del encoder primario y ensayo actual

Suite congelada6819 terminal0: **386 pruebas OK**, unittest108,800s y
global109,427s, sin fallos, errores ni omisiones.169 módulos de
`wakfu_server` cargados exclusivamente desde la copia del motor; ninguno del
checkout host. Los hashes relativos consultados antes y después vuelven a
coincidir. El primer wrapper post-run produjo hashes distintos en los tres
grupos: la auditoría confirmó que ese helper usó los caracteres `\\0` en vez
del byte NUL como delimitador. Recalculando ambos métodos sobre los mismos
archivos se reproducen exactamente ambos resultados; no hay evidencia de
ediciones en la copia congelada durante esa suite.

Build62435 terminal0: AI **`788725fce40d`**, saludable, inicio
`2026-10-07T15:20:37.020861667Z`, construido desde el `/app` completo de la
imagen viva1ed06 y el SDK completo. Incluye encoder primario, limpieza de
closures y metadatos de tamaño diferidos. World misma imagen/inicio externo
14:53:48Z, propio **1/3**. Banco **23653 terminal0**, 14 turnos, concurrencia1/2/4,
5s: **0/14 ataques**, movimientos2/2 individuales y0/12 concurrentes;
todas las invariantes pasan. Artefacto
`.runtime/local/e18-native-primary-geometry-turns.json`. Esta versión todavía
no cumple la aceptación jugable concurrente. Ningún reinicio de world por este despliegue.

### Encoder primario y liberación de grafos — validación actual

Perfil nativo34329 terminal0, artefactos
`.runtime/local/e18-native-geometry-profile.pstats` y
`.runtime/local/e18-native-geometry-profile-summary.json`: la construcción
inicial de fragmentos duplicaba encoder/parse y ocupó2,518s dentro del
encoder2,822s bajo instrumentación. No usar ese turno perfilado para afirmar
un SLA. Los fingerprints completos sumaron0,113s en10 llamadas; se conservan.

Implementación incluida en AI `788725fce40d`: la caché se siembra desde las filas
ya emitidas por el encoder primario. Cada fila se compara byte por byte
usando sus referencias globales; campos/esquemas futuros siguen el encoder
completo. La longitud diagnóstica se calcula solo si se consulta, sin otro
recorrido obligatorio al construir la caché. Se rompieron los cierres
recursivos de `query_search._sequence` y `_build_objects` para que sus
referencias se liberen sin esperar al GC. Dos regresiones comprueban la
liberación del grafo con GC desactivado, tanto al terminar como al rechazar
un ciclo. **57 pruebas dirigidas OK** antes de la última aserción de tamaño.

Medición regular posterior: construcción fría0,861s; mediana sin caché0,293s
y caliente0,074s. Bytes/SHA permanecen idénticos en la geometría real guardada
con wrapper y aliases. La instrumentación local está separada en
`.runtime/local/e18-geometry-primary-encoder-profiled-measure.json`; no mezclar
sus tiempos con los regulares. El costo frío sigue siendo mayor que el
encoder sin caché; la aceptación debe probar el turno completo.

Suite combinada histórica **6819 terminal0, 386 pruebas OK** sobre copia íntegra del motor de la
imagen viva1ed06 y del SDK actual, con todos los tests del servidor copiados;
no depende del checkout nativo que otras sesiones editan. Manifiestos de
contenido relativo: AI85 archivos `d0e299f5a047dc7397f8478504b365267baf4be2a3bbe8116f057fd5255d32dd`,
tests439 archivos `fe68df4940932060e918409f5036c3b15b4dad43a04c59e076ce2465b4b4996f`,
motor349 archivos `69081c69c64fea0d45a31efebc9e367e3887bf120f0df9fa6ffbbccec50987e2`.
Log `.runtime/local/e18-ai-primary-geometry-frozen-suite.log`.
Los resultados terminales e imports de esa suite están verificados arriba.

Nueva revisión aún sin desplegar: decodificación de tuples compartida durante
una consulta, una sola construcción de adyacencias dirigidas y caché de bytes
para tuples enteros con verificación del esquema completo. **97 pruebas
dirigidas OK**. La comparación alternada sobre el mismo grafo devuelve los
mismos21 candidatos ordenados; mediana de generación0,158s anterior y0,101s
actual. No equivale a latencia de turno. Medición regular de serialización
posterior: fría0,992s, sin caché0,442s, caliente0,109s; conserva exactamente
4.991.388 bytes y SHA34b3aa93002a. No demuestra mejora frente a otra corrida
bajo carga distinta. SDK completo copiado nuevamente al entorno congelado. Suite combinada
**75701 terminal0: 394 pruebas OK**, 163,278s unittest/164,040s global;
169 módulos nativos exclusivamente congelados. Log
`.runtime/local/e18-ai-shared-geometry-frozen-suite.log`. Guarda manifiestos
por archivo antes/después usando el mismo helper con NUL real y verifica
los imports del motor congelado. Manifiestos congelados estables; SDK85py
`4d0deee2cb598d1ca7e7267e63db9928d83e5e662a705a69d95c286fe513a938`.

Revisión posterior corrige la elegibilidad de la caché: un tuple con una lista
no debe entrar al LRU ni invocar hashes de objetos futuros. La reproducción
antes lanzaba `TypeError`; después conserva bytes, aliases y ciclos mediante
el encoder completo. Dos regresiones añadidas; **99 pruebas dirigidas OK**.
El SDK corregido se copió íntegro. Suite32007: **396 pruebas OK**,
155,641s unittest/156,328s global, cero fallos/errores/omisiones;169 módulos
nativos exclusivamente congelados. Log
`.runtime/local/e18-ai-tuple-fallback-frozen-suite.log`. Handle32007 terminal0. Manifiestos por archivo before/after idénticos
(1405 registros, cero diferencias); hashes canónicos estables: motor349py
`69081c69c64fea0d45a31efebc9e367e3887bf120f0df9fa6ffbbccec50987e2`,
SDK85py `2c97d4fb7ba4099d726a1d9b466523e5e1b89bdfc1a3c17197979b9bb9d10a81`,
tests439py `fe68df4940932060e918409f5036c3b15b4dad43a04c59e076ce2465b4b4996f`. Build94237 terminal0 y despliegue65639 terminal0: AI
**56ccebd4faee**, saludable, inicio16:03:19Z, SDK completo sobre catálogo
completo de la imagen viva1ed06. World conserva inicio14:53:48Z; propio1/3.
Banco **70638 terminal0**,14 turnos con concurrencia1/2/4, dos repeticiones,
5s reales de presupuesto; ejecutable y SDK completos congelados junto al
motor de esa misma imagen. Artefacto
`.runtime/local/e18-native-shared-geometry-turns.json`: **2/2 ataques
individuales**, movimiento y daño5 nativo7962 en ambos. Concurrencia2:
0/4 ataques,4 movimientos; concurrencia4:0/8 ataques,1 movimiento. Todas
las invariantes pasan. Duraciones individuales4,997–5,052s; concurrentes
3,953–5,185s. No equivale a aceptación del cliente ni del sistema concurrente.
En concurrencia4 dos inventarios tardaron3,245–3,268s, dejando poco margen
para transmitir/evaluar el estado; otros empezaron antes. No se reinició world.

Nueva revisión aún sin desplegar: los callers que llegan a un inventario
**encolado pero cuyo escaneo no empezó** comparten ese escaneo futuro completo,
aunque venció su ventana inicial de admisión. Llegar después del inicio sigue
creando otro escaneo; los archivos futuros siguen visibles. Regresión nueva
comprueba ambos callers, nuevo archivo y resultados independientes. Validación dirigida: **21 pruebas del puente OK**,15,989s. Suite37273
terminal0: **397 pruebas OK**,100,793s unittest/101,425s global, cero
fallos/errores/omisiones;169 módulos del motor exclusivamente congelados.
1405 registros de manifiesto before/after idénticos; SDK85py canónico
`9b6ce3966c6ec9b040b4c11432ed61b0d08ff0d791f0db01becfe6e38fa388f2`.
Log `.runtime/local/e18-ai-queued-inventory-frozen-suite.log`.
Build/despliegue40081 terminal0, AI **a007dedbfd69**, inicio16:10:00Z;
catálogo completo de la imagen viva1ed06 y SDK completo. World mismo inicio,
propio1/3. AI saludable. Banco **48172 terminal0**,14 turnos1/2/4,2 repeticiones
y5s reales, SDK completo congelado con mismo motor de la imagen viva.
Artefacto `.runtime/local/e18-native-queued-inventory-turns.json`:2/2 ataques
individuales,0/4 con2 (4 movimientos),0/8 con4 (0 movimientos); invariantes
intactos. Individuales4,727–5,196s; concurrentes4,525–5,207s. En4 llegaron8
búsquedas a AI, pero solo se expandió0–1 candidato por búsqueda: el tiempo
restante seguía agotándose en preparación y consultas nativas. Dos inventarios
aún tardaron3,515/3,791s; el resto0,569–0,838s. No demuestra aceptación
concurrente ni mejora aislada de latencia. Sigue pendiente esa aceptación.
Se audita el costo de previews/RNG y transporte íntegro; world no se modifica.
Perfilado diagnóstico: intentos90005 y50213 terminal1 por conflicto de perfiles
simultáneos (`Another profiling tool is already active`), no son evidencia de
rendimiento ni fallos de combate. Captura corregida **31589 terminal0** sobre un
solo `run_shared_turn`, excluye prewarm, transferencia inicial del catálogo y
verificación posterior del banco; sus tiempos instrumentados no son SLA.
Artefactos `.runtime/local/e18-native-single-turn-profile.pstats` y
`e18-native-single-turn-profile-summary.json`: en turno instrumentado,
NativeSession inicial3,701s; registrar contexto2,123s; encoder2,034s;
inventario1,478s. `Path.relative_to` acumuló0,947s en11.160 llamadas. No
comparar ese tiempo instrumentado con el ensayo regular.

Nueva revisión aún sin desplegar conserva las rutas relativas durante el
recorrido `scandir`, evitando recalcular ancestros por archivo y preservando
el orden anterior de `Path`. Sigue recorriendo todos los archivos, firmas,
bytes, hashes y aliases. **22 pruebas del puente OK**,16,169s; regresión nueva
verifica orden jerárquico, archivos ocultos/futuros y cada byte congelado.
Comparación alternada58453 terminal0: manifiesto íntegro de11.160 entradas
idéntico en8 muestras alternadas del mismo proceso; mediana anterior0,547s
y actual0,174s (snapshots físicos calientes). SHA manifiesto
`66d9977c15e85ec595ee284d21994ad937f7d6384a22df61a02fac1eaeb0a88a`.
Artefacto `.runtime/local/e18-relative-inventory-controlled.json`. No es
latencia de turno ni compara corridas independientes. SDK completo copiado
para suite congelada398. **66211 terminal0: 398 pruebas OK**,105,153s
unittest/105,888s global, cero fallos/errores/omisiones;169 módulos
exclusivamente congelados.1405 registros before/after idénticos. SDK85py
canónico `6dbb74f05305f6e45278af03d0573d3d7a95baf52ff03cad4a4369338799854e`.
Log `.runtime/local/e18-ai-relative-inventory-frozen-suite.log`.
Build/despliegue86129 terminal0: AI **24e30ebf9eeb**, inicio16:25:59Z,
SDK completo sobre catálogo completo de la imagen viva1ed06. World mismo
inicio14:53:48Z; propio1/3. AI saludable. Banco **91003 terminal0**:
14 turnos1/2/4,2 repeticiones,5s reales; SDK completo congelado. Ataques2/2
individuales y1/4 con2 (3 movimientos);0/8 con4 (0 movimientos). Invariantes
intactos. Individuales4,721–4,892s; concurrentes3,531–5,030s. Artefacto
`.runtime/local/e18-native-relative-inventory-turns.json`. Inventario individual
0,198–0,204s; con4 dos casos aún3,148/3,469s y los demás0,246–0,631s.
No acredita consistencia concurrente ni mejora aislada de corrida completa.

Experimento privado **21492 terminal0**, mismo banco íntegro y presupuesto real,
encoder ordinario completo con `_geometry_cache=False` únicamente en el
proceso del banco; servicio desplegado intacto. Conserva todo el grafo, campos,
nodos y aliases. Compara jugabilidad sin el costo inicial de construir caches
derivadas; no recorta el contexto ni desactiva guards/reglas nativas. Artefacto
`.runtime/local/e18-native-uncached-geometry-turns.json`:2/2 ataques
individuales,0/4 con2 (3 movimientos),0/8 con4 (0 movimientos); invariantes
intactos. Turnos3,374–5,496s. Eliminar caches derivadas no resolvió la
aceptación concurrente. No elegir ese cambio para producción ni atribuir una
comparación aislada de latencia entre estas corridas bajo carga distinta.
Se conserva la revisión desplegada. Próximo foco: evitar la repetición de
serialización/transferencia/verificación del terreno idéntico en cada preview
mediante representación íntegra por contenido, sin cambiar el puente world.

### Última validación y despliegue

Repetición combinada terminada: **381 pruebas OK**, 147,864 s de unittest
(148,539 s global), exit0. AI y `combat_retained_runtime.py` conservaron sus
hashes; el manifiesto de todo `wakfu_server` cambió durante la corrida por
trabajo externo. No acredita un checkout nativo inmutable. Primera corrida
AI sola preservada en `.runtime/local/e18-ai-geometry-suite-first.log`.

Build97636 terminal0, AI nuevo **`befd1af16751`**, saludable, inicio
`2026-10-07T14:58:48.73092073Z`; construido exclusivamente desde la imagen
viva `1ed06b10b4d2` y SDK completo actual. World saludable, inicio externo
14:53:48Z; contador propio **1/3**. Banco nativo **11476 terminal0**, 14 turnos,
concurrencia1/2/4, presupuesto5s. SDK completo copiado antes de la corrida
al mismo árbol congelado del motor; salida prevista
`.runtime/local/e18-native-geometry-fragment-turns.json`: ataques **1/2**
individuales, **0/4** con concurrencia2 y **0/8** con concurrencia4; todos los
invariantes pasan. Individuales3,91–5,04s; con2:4,59–4,78s; con4:4,76–5,16s.
Prewarm54,706s y primer catálogo15,867s fuera de los turnos, identificados
por separado. No es una comparación aislada de rendimiento con versiones
anteriores. La aceptación concurrente sigue pendiente.

En el segundo individual la búsqueda cerró sin expandir por presupuesto
local (1128ms medidos en el último corte,250ms disponibles); preparación
8,67ms y espera63,58ms. Con2 la primera búsqueda comenzó a3,38–3,91s del
turno; con4 varias agotaron el plazo verificando catálogo. Hay evidencia de
costos adicionales a la serialización. Siguiente paso: perfil nativo de un
turno con el mismo SDK/motor congelados; no modificar world ni recortar
contexto, catálogo, referencias o validaciones para ocultar esos costos.

### Preparación de geometría — trabajo actual

Integración en `native_context` de fragmentos derivados para el tipo nativo
exacto `ImmutableTerrainSet`. El encoder completo sigue disponible y se usa
para formas/campos futuros. Cinco regresiones de integración verifican uso
real de la caché y bytes idénticos del grafo con aliases, ciclos y campos
futuros; trece pruebas del helper pasan. Desplegado en `befd1af16751`; banco nativo en ejecución.

Medición local con las 7.075 celdas y 24.556 aristas del grafo real guardado,
en un wrapper con referencias compartidas: 4.991.388 bytes idénticos;
mediana sin caché 0,282 s y caliente 0,068 s. Primera construcción 1,506 s,
aún costosa: la optimización posterior no acredita una mejora de ese costo. Artefacto
`.runtime/local/e18-geometry-fragment-measure.json`. Esta medición solo cubre
serialización de geometría: no acredita mejora del turno completo ni de
concurrencia. Pendientes suite completa, rebuild exclusivo de AI y banco
nativo con SDK/motor congelados de la misma imagen. La suite completa actual terminó a cargo de Luna, con hashes antes/después y log en
`.runtime/local/e18-ai-geometry-suite.log`.

### Hecho

Último cambio desplegado: AI `bd7d711f99f0`, saludable, build30067 terminal0,
inicio `2026-10-07T14:29:33.487048232Z`. Incluye topología derivada reutilizada,
provider aislado de utilidad v3, commit directo con guard y encoder reutilizado.
Suite363 OK,49 dirigidas posteriores OK. Banco74685 terminó137 durante
prewarm; world cambió de imagen/inicio mientras se ejecutaba. No hubo
resultado ni artefacto acreditado; no atribuirlo a OOM sin evidencia
(consulta de eventos OOM vacía). Este agente no reinició world.
Puente y volumen verificados en nueva imagen. AI reconstruido desde esa
imagen viva completa. Copia íntegra de `/app` en
`.runtime/e18-world-native-1ed06b10b4d2`; banco74384 activo en host contra el
mismoAI por HTTP, usando exclusivamente ese motor copiado. Salida
`.runtime/local/e18-native-extended-handoff-host-turns.json`; proceso74384
terminal0.0/14 ataques, movimientos1/2,4/4,2/8; invariantes intactos.
Primer individual seleccionó cast después de mover, pero venció antes de
commit; segundo cerró sin expandir. Diferente motor/ubicación/carga respecto
a88495: no comparación aislada de rendimiento. Falta aceptación jugable
distante en la versión actual. Es prueba privada, no partida conectada.
Nueva evidencia de corte (sin cambiar límites): stopReasons y trabajo en el
último check;47 pruebas dirigidas OK /0,473s. Build30067 terminal0 y healthy.
Banco12850 terminal0,14 turnos, SDK copiado junto al motor para que catálogo y
bytes ejecutados compartan raíz. Salida
`.runtime/local/e18-native-frozen-sdk-budget-evidence-turns.json`.
Resultado2/2 ataques individuales,0/4 con2 y0/8 con4; movimientos2/2,2/4,0/8.
Todos los invariantes pasan. Individuales4,962–5,092s; concurrentes3,481–5,258s.
StopReasons demuestra corte por decision_wall_budget, no búsqueda local:
trabajo en último check0–83ms de250ms; preparación/espera consume la fracción
de tiempo total. El siguiente ajuste en implementación intenta reutilizar
serialización completa de terreno congelado preservando nodos/alias/referencias
exactos; tipos/campos futuros deben conservar camino completo sin cache.

Resultado anterior AI `eba5c0c628af`, build15540 terminal0:
Repertorios grandes alternan todos los hechizos con movimiento; inventarios
simultáneos comparten un recorrido completo solo si entraron antes de su
inicio.50 pruebas dirigidas y341 conjuntas OK. Ensayo nativo actual88495:
14 turnos con concurrencia1/2/4, artefacto recuperado en
`.runtime/local/e18-native-batched-alternating-turns.json`. Resultado:
ataques2/2 individuales,0/4 con2 y0/8 con4; movimientos2/2,4/4 y2/8.
Todos los invariantes pasan. Turnos concurrentes4,232–5,320s; no acredita
ataque concurrente ni SLA. Proceso88495 terminal0.
World mantiene imagen e inicio y el contador propio sigue1/3.

Diagnóstico del artefacto nuevo: con2, el primer plan certificado contiene
solo movimiento y la segunda búsqueda empieza3,891–4,555s, demasiado tarde
para certificar y comprometer cast. Con4 ya hay8 búsquedas (antes0), pero
varios turnos agotan el plazo antes de comprometer movimiento. El inventario
en lotes iniciales tarda0,32–0,36s; quienes entran después recorren otro lote
y esperan1,54–1,99s. Reducir trabajo duplicado de preparación/preview y
replanificación completa sin recortar contexto sigue pendiente.

Ampliación posterior a88495, pendiente de batería conjunta y nuevo build:
topología cachea solo la adyacencia derivada del tipo nativo congelado;
ocupación, HP y distancias se recalculan por estado.15 pruebas dirigidas OK.
Sobre7075 celdas/24556 aristas idénticas, reconstrucción de adyacencia12,71ms
mediana frente a0,009ms reutilizada; solo esa operación, no un turno completo.
El driver evita el preview redundante previo al commit inmediato; mantiene
guard antes del commit y commit nativo transaccional.29 pruebas dirigidas OK
con topología, incluyendo fuente cambiada, deadline y acción rechazada.
Extensión de utilidad v3 en revisión: mapas explícitos con pesos y delta
firmado solo si hay medición raíz/estado; ausencia declara desconocimiento.
El proveedor opera sobre copia privada completa y rechaza mutaciones;
configuración explícita incluida en autoridades/fingerprint. Ausencia no
infiere mecánicas.27 pruebas dirigidas de extensión OK; suite49842 terminal0:
**363 pruebas OK /98,810s**,99,377s globales, hashes AI y archivo nativo
iguales antes/después. Log `.runtime/local/e18-ai-extended-suite.log`.
Después se reutilizó JSONEncoder por grafo:49 pruebas dirigidas OK /0,407s;
en geometría completa,5.462.725bytes exactamente iguales, mediana de
serialización0,367s anterior/0,307s nueva (solo esa operación).
Build exclusivo deAI73190 iniciado para el conjunto; sin reinicio deworld.

Evidencia anterior, en orden de implementación: decodificación de geometría verificada
contra los datos y hashes originales; preparación completa del contexto
separada del presupuesto local de búsqueda, conservando el plazo real del
turno; catálogo completo congelado en una copia privada verificada una vez
por versión, con detección de cambios del archivo privado. Pasan 23 pruebas
de búsqueda y 33 pruebas dirigidas de catálogo. La batería completa terminó:
**321 pruebas OK**, 78,249 s, sin fallos, errores ni omisiones. Despliegue
exclusivo de AI terminado y `/health` responde correctamente. El nuevo banco
real terminó (sesión84576, exit0), artefacto
`.runtime/local/e18-native-sealed-context-turns.json`: **0/14 ataques**,
solo un movimiento en la cohorte de dos turnos simultáneos. Todos los
invariantes pasaron. Inventario/verificación del catálogo individual bajó
a 0,29–0,31 s, pero la decodificación diferida de aristas consumió el
presupuesto local antes de probar movimiento. Corrección posterior desplegada:
contar esa decodificación completa como preparación, dejando
rutas, ordenación y evaluación bajo el presupuesto de exploración. Pasan
25 pruebas dirigidas y **323 pruebas conjuntas OK** (132,542 s; sin fallos,
errores ni omisiones); despliegue exclusivo de AI terminado y saludable.
Nuevo banco real terminado (sesión84693, exit0), artefacto
`.runtime/local/e18-native-lazy-preparation-turns.json`: 0/14 ataques;
movimientos 2/2, 1/4 y 0/8 por cohorte. Todos los invariantes pasaron.
Ambos turnos individuales seleccionaron un plan nativo move+cast válido,
pero siguieron explorando alternativas hasta dejar tiempo solo para mover.
El siguiente ajuste, desplegado en `3968bd5de686`, fija un límite de tiempo por
decisión (`searchTimeFraction`, defecto0,5) para dejar margen a ejecución
y replanificación después de cada acción real. Incluye consultas y toda
preparación; no renueva el plazo con respuestas posteriores. Pasan27 pruebas
dirigidas y **325 pruebas conjuntas OK** (74,134 s, sin fallos, errores ni
omisiones); despliegue exclusivo de AI terminado, saludable. Banco real
sesión66297 terminal0, artefacto `.runtime/local/e18-native-decision-wall-turns.json`:
**2/2 ataques individuales**, movimiento y cast7962 reales, 4,85–5,03 s;
**0/4 y 0/8 ataques concurrentes**. Todos los invariantes pasaron.
Prewarm174,21s y primer catálogo6,93s fuera del tiempo de turnos; coexistían
otros contenedores de pruebas nativas intensivas. No acredita rendimiento
concurrente ni aceptación GUI. Ya hay evidencia para probar la partida
completa de Wonejos documentada en `PRUEBA-WORLD.md`; se continúa optimizando
preparación y validación para concurrencia.

Cambios posteriores desplegados en `76436fb692fe`: reutilizar en la búsqueda el grafo
inicial ya leído y validado, sin cache de archivos mutables ni campos nuevos
en el payload; recorrer el catálogo con `scandir`, manteniendo todas las
rutas, hashes y guards de identidad. Pasan42 pruebas dirigidas, incluyendo
rechazo de corrupción CAS, archivos ocultos/futuros, enlaces de archivos y
rechazo de ciclos de directorios enlazados. Comparación de enumeración del
world vivo: **5.673 archivos idénticos**, 74ms con recorrido anterior y28ms
con el nuevo; no mide el turno completo. Batería conjunta sesión30624 terminal:
**328 pruebas OK**, 164,937 s, cero fallos, errores u omisiones. Despliegue
exclusivo de AI terminado y saludable. Banco real sesión30773 terminal0,
artefacto `.runtime/local/e18-native-root-reuse-scandir-turns.json`:
2/2 ataques individuales en4,80–4,84s, 0/4 y0/8 concurrentes; movimientos
2/2,4/4,0/8 respectivamente. Todos los invariantes pasaron. Prewarm111,49s
y primer catálogo7,26s fuera del tiempo de turnos.

Ampliación posterior desplegada en `8cac53cf86bc`: versiones de catálogo comparten
referencias a bytes completos ya congelados; solo los hashes nuevos se
copian/verifican en un archivo delta. Toda versión conserva su mapa íntegro
de blobs y aliases. Se comprueban identidades de archivos privados por
archivo, incluyendo llamadas repetidas a seal; los métodos canónicos siguen
recalculando hashes. Validación de referencias sin sets temporales mantiene
los rechazos de referencias vacías, extras, mixtas y tipos/índices inválidos.
64 pruebas dirigidas OK. Mediana local de validación del mismo grafo de
73.855 nodos:103ms anterior/72ms nueva; no mide turnos completos.
Batería conjunta sesión17757 terminal: **332 pruebas OK**, 161,220s,
cero fallos, errores u omisiones. Despliegue exclusivo de AI terminado y
saludable; banco real activo sesión49663, salida
`/data/e18-native-frozen-delta-turns.json`. World sin reinicio propio adicional.
Salida del banco: 2/2 ataques individuales, 0/4 con concurrencia2 y
0/8 con concurrencia4; prewarm147,47s y primer catálogo18,39s fuera de
turnos. La cohorte de4 registró entre67,93 y93,69s por turno sin llegar
a solicitar búsqueda a AI. El proceso49663 terminó con salida0; artefacto
recuperado en `.runtime/local/e18-native-frozen-delta-turns.json`.
La consulta independiente `docker top` terminó después de una demora
prolongada. La observación de `/proc` registró el banco con1.785.056kB
residentes y2.411.760kB en swap; otros contenedores estaban consumiendo CPU
y memoria. Esto documenta carga externa, no demuestra que toda la demora
sea ajena al sistema AI. Sin reinicios.
Durante esa incidencia se continuó con cambios locales de AI: alternar un
candidato de hechizo y uno de movimiento, rotando entre todos los hechizos.
No se elimina ninguna celda, ruta ni hechizo. Pasan **30 pruebas dirigidas**:
repertorio de20 hechizos mantiene todos sus blancos; tres previews bastan
para move+cast con el primer hechizo soportado; el último también compite
tras19 hechizos explícitamente sin soporte. Cambios todavía sin desplegar.
El ensayo49663 conserva valor para invariantes y diagnóstico de incidencia,
pero no es una comparación aislada de rendimiento por carga externa y
cambios de catálogo durante su ejecución. Está implementada, sin desplegar,
la agrupación de solicitudes de inventario durante una ventana de2ms
anterior al recorrido. Las solicitudes posteriores fuerzan otro recorrido
completo; cada solicitante conserva su plazo y recibe su propia copia del
manifiesto. Pasan10 pruebas dirigidas, incluidos plazos vencidos y archivos
creados después de cerrar un lote. La batería dirigida conjunta de inventario
y búsqueda terminó con **50 pruebas OK /18,830s**. Batería completa actual
sesión75552 terminó con salida1: errores nativos en el checkout compartido
por `UnboundLocalError` de `identity` en `combat_retained_runtime.container`.
El total no quedó recuperable por truncamiento de salida; no acreditar esa
batería. Una lectura posterior ya muestra la asignación corregida por otra
sesión; este agente no cambió el motor de world. Se repite la batería con
captura íntegra en `.runtime/local/e18-ai-current-suite.log`: sesión9590,
**341 pruebas OK /166,317s**, 166,897s globales, cero fallos/errores/omisiones.
El wrapper terminó1 por usar una variable readonly de zsh después de terminar
Python; el footer de unittest confirma la batería verde. El hash del archivo
nativo cambió entre las mediciones: no acreditar una versión inmutable del
checkout. El ensayo siguiente usa el motor de la imagen viva, conservada sin
reconstruir el checkout compartido. Build exclusivo de AI15540 terminal0, health aprobado; ensayo88495
terminal0 documentado arriba.

- Un solo servicio AI y Dockerfile con `COPY . /app`. `rebuild.sh` toma el
  catálogo completo de la imagen del world vivo y reinicia exclusivamente AI.
  Último despliegue AI: imagen `bd7d711f99f0`, build30067 terminal0,
  inicio `2026-10-07T14:29:33.487048232Z`, health aprobado. Incluye
  alternancia, inventarios, topología derivada, utilidad v3 y commit directo. World conserva
  el puente y volumen; reinicios propios1/3. Ensayo nativo de14 turnos12850 activo,
  salida `.runtime/local/e18-native-frozen-sdk-budget-evidence-turns.json`; no editar SDK ni
  reconstruir AI mientras ese ensayo esté activo.
- Catálogo sin filtros de monstruos, ataques, mapas o extensiones. Copia
  histórica verificada: 11.029 entradas / 689.354.892 bytes (incluye rutas
  alias; el almacenamiento deduplica por contenido). Transporte completo
  por hashes/bloques, sin límite al tamaño total. El exportador ahora congela
  los bytes inventariados para evitar corrupción si cambia un archivo fuente.
- Grafo íntegro de runtime, actores, autoridades, perfiles, campos futuros,
  referencias compartidas y ciclos. Compresión sin pérdida y guard de fuente
  completo con recorrido de contenedores en C; no ejecutar reducers nativos.
- SDK en `server/ai-service`: carga de todos los participantes/builds,
  perfiles completos congelados por encuentro, loader privado con recarga,
  consultas nativas de repertorio/movimiento/cast/LOS/turnos, búsqueda v3,
  riesgo rival explícito, certificación fresca y commit transaccional con ACK.
- Última suite conjunta de AI y regresiones del servidor: **307 pruebas / 123,175 s**
  (123,742 s de ejecución total; cero fallos, errores u omisiones).
  El adaptador genérico pasó además 22 pruebas dentro de la imagen real
  de world, sin iniciar otro servicio de juego. El preparador del puente
  verifica que solo reemplaza la función acordada y conserva el resto del archivo. Incluye reemplazo de
  callbacks antiguos, huella rápida de commit, encoder de invocaciones,
  serialización completa por nodos, reutilización del catálogo entre acciones
  y rutas completas certificadas por el motor nativo.
  Regresión del servidor previa: **28 pruebas / 62,103 s**.
- Ensayo HTTP real con **7.075 celdas completas** y perfil normal `{}`:
  selecciona ataque7962 de Wonejo, sin mutar la fuente. Último ensayo con
  catálogo reutilizado: **2,272 s de decisión y 0,350 s de preparación**.
  Sin reutilización: **2,285 s y 1,406 s**, respectivamente. El encoder produce
  exactamente los mismos bytes del grafo completo; en este ensayo desapareció
  la pausa de 9–18 s observada en registros anteriores. El ensayo posterior del turno completo ordinario con presupuesto de5s
  confirmó un ataque a los4,456s; el cierre por fallback terminó a los5,256s.
  Tras optimizar la validación íntegra del catálogo, el ensayo compartido
  confirmó ataque a los4,209s y publicación del cierre a los5,316s; el ACK
  quedó pendiente del cliente. La preparación fue1,690s. El foco confirmado llegó al servicio y las17
  comprobaciones de integridad pasaron. Estos datos
  todavía no acreditan el flujo v3 en el juego ni un límite duro de latencia. El ensayo anterior pasaba turno porque la
  preparación agotaba los250ms; ahora el presupuesto de exploración comienza
  tras cargar el primer repertorio/grafo completo. Los límites de nodos,
  consultas y turno siguen vigentes.
- Serializador por autoridad propia para múltiples PC/NPC e invocaciones
  registradas; ocho pruebas enfocadas de entrada/estadísticas pasan. Prueba
  diferencial con JAR confirma consumidor12873 sobre UID positivo de summon;
  la evidencia distingue la aplicación de datos de los observers gráficos.

- Registro de equipo v3 dentro de AI: foco e historial reciente de resultados
  nativos publicados, con aislamiento por UUID/equipo, expiración y revisión.
  Se confirma después de todos los envíos locales o del broadcast compartido
  y su barrera ACK; previews, fallos y lotes vacíos no escriben memoria.
  El historial coordina32 transiciones recientes; el ledger nativo completo
  permanece intacto. El checkpoint existente conserva los campos del Fight;
  el backend actual aborta combates interrumpidos, no los reanuda.
- Capacidades observadas por hechizo a partir de previews certificados:
  daño, curación, protección, control, desplazamiento e invocación registrada.
  Una habilidad puede tener varias; no se inventa una capacidad por ID/nombre.
  El relevamiento se declara parcial y no añade un bonus al score por etiqueta.
  Suite conjunta254 completa aprobada; ajuste posterior de registro de bajas/curación:
  32 pruebas enfocadas aprobadas.

- Posición v3 usa distancias de la topología dirigida XYZ del snapshot nativo,
  no solo cercanía en XY. Prioriza la escalera correcta sin eliminar rutas
  alternativas; footprint, costes y LOS siguen certificados por preview.
  No añade bonus por altura. Geometría ausente se declara desconocida; aristas
  fuera de walkable se rechazan. Snapshot viejo sin el nuevo campo conserva
  el fallback XY, identificado explícitamente en `positionEvidence`.
- La muerte del actor durante un preview no recibe mejora de posición.
  44 pruebas enfocadas aprobadas; suite conjunta posterior de240 pruebas aprobada.
- Transporte de catálogo parcialmente actualizado: usa la lista de hashes
  faltantes del manifiesto ya verificado, sin volver a consultar todos los
  assets. La validación final rehasha el catálogo íntegro. Prueba HTTP real
  con300 archivos provisionados y uno cambiado: solo manifiesto+archivo nuevo
  transferidos, las300 entradas completas.

- Búsqueda ampliada en el SDK: conserva el mejor estado y alternativas por
  intención/objetivo antes de llenar el beam con ramas repetidas. Ordena
  blancos de siguientes previews por capacidades observadas, sin excluir
  celdas ni sumar bonus de rol. Regresión integrada: curación inicialmente
  menor que dos ataques conserva una continuación y gana por resultado.
  24 pruebas enfocadas aprobadas; suite conjunta243 aprobada más la continuación nueva aislada. Cambio desplegado en AI y health aprobado.

- Reservas blandas de corredores de tiro en SDK: se derivan de probes LOS
  nativos de un cast enemigo elegido que requiere LOS; cubren todos los Z
  walkable del XY comprobado. Solo se confirman tras publicación y se
  comparten con otros aliados. Posición, muerte, turno del dueño, TTL,
  revisión, instancia y blockers invalidan la reserva. El score usa la
  huella nativa, incluidos actores que LOS ignora. No inventa rayos.
  Suite conjunta254 aprobada y49 focales posteriores; estas incluyen
  coordenadas corruptas y una prueba con rayos nativos reales de Amakna.
  Capa desplegada en AI con health aprobado. Nuevo ensayo completo: ataque4,829s, cierre/publicación5,024s,15guards
  intactos y9paquetes FIFO. Wonejo no creó reserva en este caso.

- Previews v3 conservan ahora la transacción completa, paquetes binarios,
  acción y fuente en el mismo grafo del runtime. Las referencias compartidas
  entre transaction.fight y runtime.fight se conservan. Se declara
  `uncommitted_native_preview`; estos paquetes nunca autorizan una entrega.
  La identidad del runtime se separa del hash del recibo para deduplicar
  búsqueda y riesgo sin perder recibos.50 focales y suite260 aprobadas;
  medición nativa nueva: cast4,146s/publicación5,307s y17guards intactos.
  Ampliación desplegada en AI, health aprobado.

### En curso

Banco concurrente real desde el contenedor world contra AI desplegado, sin
otro servicio ni ACK simulado.14 turnos en cohortes1/2/4, IDs numéricos iguales
y UUID/datos futuros distintos: fuente, publicación única y barrera ACK
correctas, pero rendimiento insuficiente antes de las nuevas optimizaciones:
ataques1/2,0/4 y0/8; con4 ni siquiera inició consultas. Artefacto preservado
en `.runtime/local/e18-native-concurrent-turns-baseline.json`. Los percentiles
de ese corpus pequeño no acreditan SLA.
Se corrigió preparación de candidatos (aristas de movimiento diferidas hasta
explorar esa stream) e inventario (identidad física stat sin resolver rutas
repetidamente). Se conservan todos los datos/archivos/rutas y rehash íntegro.
Suite284 aprobada y AI ac8c8ca87419 desplegado/healthy. Además, los hashes
de blobs canónicos se verifican en paralelo, manteniendo SHA completo,
escrituras/publicación atómicas y doble verificación de read; sin cache de
hashes aprobados. Se coteja identidad del descriptor antes/después de leer
un archivo y del path final. Nueva medición: ataques2/2 individuales,1/4 con2
combates,0/8 con4; las8 búsquedas de la cohorte4 sí comenzaron.14 turnos sin
fallos de aislamiento/publicación/ACK, pero el rendimiento concurrente sigue
insuficiente. El ensayo distante terminó: 0/2 movimientos o ataques,
2 decisiones end_turn en 3,130/2,952 s, sin fallos de aislamiento. La búsqueda
expandía solo el cast fuera de alcance: la espera nativa consumía el presupuesto
de 250 ms antes de explorar movimiento. Artefacto:
`.runtime/local/e18-native-distant-turns.json`.

Corrección desplegada en AI `a8f4ea3c9072` (world conserva inicio10:38:41Z): pausar únicamente el reloj
de trabajo de búsqueda durante sus consultas nativas; conservar el plazo
real del turno. El SDK envía duración restante `nativeBudgetMs` en contexto
y respuestas admitidas/rechazadas, con reserva de commit configurable
(default 500 ms). La predicción rival mantiene su plazo completo, acotado
además por esa reserva. 15 regresiones de búsqueda aprobadas, incluyendo
esperas mayores de250 ms, movimiento tras cast rechazado y hints inválidos.
Suite conjunta:288 pruebas OK /82,521s (83,105s total), más el módulo
actualizado de búsqueda15/15 OK /0,021s para cambios posteriores a la
colección de la suite. El nuevo ensayo HTTP distante terminó sus2 turnos: movimiento real
publicado en1/2, ataques0/2, tiempos5,023/4,663s, sin fallos de aislamiento.
La búsqueda sí exploró movimiento (expanded10 en el primer caso), pero
varios casts sin daño a celdas vacías consumieron el plazo antes de explorar
movimiento+ataque y dejaron reservas insuficientes para commit en otro caso.
Artefacto `.runtime/local/e18-native-distant-budget-turns.json`. Aproximación
mejorada, aceptación completa todavía pendiente; siguiente paso: distribuir
la exploración entre continuaciones prometedoras sin agotar la raíz.

En validación: scheduler incremental con `probeQuantum=2`. Conserva cada
stream de acciones y el repertorio completo para reanudarlo; tras un quantum
explora continuaciones certificadas antes de seguir la raíz. 17 regresiones
de búsqueda OK /0,026s: con3 previews encuentra movimiento+cast; con
depth1 y quantum1 sigue explorando todas las celdas sin refetch de repertorio.
Suite conjunta293 OK /90,323s (90,938s total). Scheduler desplegado
AI `b9acc96d742d`; ensayo distante sesión84219 terminal0. Prewarm
fuera de los turnos650,793s bajo la demora de Docker; no es SLA de combate.
Caso válido: movimiento+ataque publicados en5,028s. Segundo caso rechazado
en3,464s por fixture incorrecto: PV modificados después de instalar snapshot
nativo. Se corrigió fixture para construir HP variable antes de instalación
y se añade preflight de características nativas de todos los actores.
Regresión4/4 OK /3,159s. El ensayo previo budget también contiene un rechazo
de ese tipo; los bancos históricos sin validación de fixture no acreditan
por sí solos rendimiento general. Artefacto completo preservado en
`.runtime/local/e18-native-distant-quantum-turns.json`. Docker y /health
volvieron a responder; imagen/inicio world e839fd35a2c1/10:38:41Z, sin
reinicio propio. Consulta de procesos34212 terminal1 por formato pcpu no
soportado; no representaba caída del proceso nativo.
Ajuste posterior desplegado: beam global sobre todas las
continuaciones (el cursor raíz se conserva aparte), prioridad inmediata de
un quantum para hijos raíz y cola justa para continuaciones profundas.
19 pruebas de búsqueda OK /0,038s; revisión sin bloqueo determinista del
cursor raíz, conservando soporte y diversidad de orientación. Los contadores
expandedByDepth y peakContinuationFrames permiten comprobar cobertura real.
Suite conjunta nueva307 OK /123,175s (123,742s total), sesión30761
terminal0. Ajuste desplegado en AI4aa49a03651c, saludable. Nuevo banco
HTTP distante con fixtures verificados, cohortes1/2/4 ×2, sesión54895
terminal0.14 turnos: ataques0/14; movimientos2/2 individuales,2/4 con2
encuentros,0/8 con4. Todos los invariantes de fixture/fuente/publicación/ACK
pasaron; esto no acredita aceptación táctica. Tiempos4,428–5,354s.
Prewarm31,020s y transferencia catálogo6,037s fuera de los turnos.
Artefacto `.runtime/local/e18-native-fair-concurrent-valid-turns.json`.
La cohorte4 gastó2,809–3,187s en inventario/verificación y comenzó HTTP
entre4,059–4,499s. Los individuales movieron, pero reabrir una búsqueda
tras el movimiento agotó el plazo antes de atacar. Solo hubo profundidad1
(expanded2), porque decodificar la siguiente posición agotó presupuesto
activo. Próximo paso: medir y reducir decodificación duplicada de geometría
completa y verificación del catálogo, manteniendo los datos y guardas.

También se identificó una serialización global: `QuerySessions.decide`
mantiene un RLock común durante rehash completo del catálogo, lectura del
grafo y resume del generador, bloqueando encuentros independientes. Se
prepara cambio de bloqueo por sesión con registro global corto, sin reducir
validación, datos, aislamiento ni garantías de retry/cancel/TTL. Snapshot8407800e851c,689.728.418bytes.
Sin reinicio world.

Nueva ampliación validada en código: rutas hacia aliados vivos heridos se
intercalan con aproximación a enemigos, conservando todos los candidatos.
El beam reserva una continuación que mejora la distancia dirigida XYZ al
aliado, sin bonus. Una regresión con beam2 selecciona movimiento por una
escalera y curación legal solo desde esa posición; sin curación útil no
selecciona esa ruta por recibir un premio. Es un oráculo de contrato de pruebas,
no evidencia de que los NPC actuales ya dispongan de curación ejecutable.
Una prueba adicional con NativeOracle real selecciona rodeo+ataque BACK por
mayor daño nativo, conserva el estado fuente y no usa bonus de orientación.
Suite conjunta276 aprobada. Medición HTTP posterior: ataque4,738s/cierre
publicado5,029s,15 guards intactos y9 paquetes FIFO; ACK pendiente sin cliente
simulado. Ampliación desplegada en AI `58413db8dc02`, health/loader aprobados.
Catálogo:11048 entradas/689711986 bytes, `65c45a2cc2778bff`, rehash íntegro,
ningún objeto faltante. World no se reinició. Falta cubrir apertura lateral
de LOS y protección con HP lleno.

Captura completa del callback de daño nativo ya desplegada: FRONT/BACK/SIDE
observado y localización aplicada por el efecto, sin bonus inventados.
Conserva estado, daño, paquetes y RNG frente al preview original. Si falla
la captura, marca evidencia desconocida y conserva el resultado nativo.
World mantiene su inicio `2026-10-07T10:38:41.858065287Z`: sin reinicio propio.

Puente final desplegado y saludable; aceptación conectada al juego todavía
pendiente. Snapshot histórico del catálogo desde world y SDK: **11.050 entradas
/689.726.240 bytes**, sin objetos faltantes; manifiesto `aed0b136d087cec4`. El almacén de
AI rehashó todos sus objetos. Las cifras corresponden a ese snapshot; el
SDK puede evolucionar después y producirá un nuevo manifiesto. La primera preparación de una sesión
fría puede consumir el presupuesto y cerrar por fallback; no se acredita un
límite duro de latencia. El ataque registrado de invocaciones conserva la
restricción nativa de lifecycle aún no auditado; no se ha saltado esa validación.

### Después

1. Ejecutar la [prueba manual general](../../../server/ai-service/docs/PRUEBA-WORLD.md)
   y cotejar acciones, FIFO, ACK y cierre contra logs del juego.
2. Completar roles derivados, coordinación por equipo, orientación y corpus
   concurrente usando resultados nativos. Todo cambio de lógica queda en AI.
3. Continuar midiendo turnos completos y fallos de servicio sin recortar
   contexto ni introducir ataques específicos por especie.

Restricciones: no modificar cliente ni checkpoint de persistencia; preservar
los cambios de otros agentes. Máximo **tres reinicios de world** para este trabajo;
contador de este agente: **1/3**, sin reiniciar el contador al reiterar la restricción. Avisar antes de cada reinicio;
después del tercero no hacer más cambios. Catálogo completo no significa que
el motor ejecute todos los efectos futuros: dependencias obligatorias sin
soporte se declaran explícitamente.

Evidencia: [validación](../../../server/ai-service/docs/VALIDACION.md),
[catálogo Docker](../../../server/ai-service/docs/CATALOGO-CONTENEDOR.md),
[inventario del puente](../../../server/ai-service/docs/BRIDGE-INVENTORY.md).

La línea base anterior acercaba al enemigo por BFS y añadía un ataque específico de Wonejo. La implementación táctica en curso permite comparar consecuencias nativas y redecidir tras cada acción. Referencia: reutilizar la arquitectura táctica de `/Users/hectorpulido/dofus/ai-service`, excluyendo Laya, con adaptadores nativos de Wakfu para hechizos, terreno 3D, orientación y ejecución.

[Estado y sistemas reutilizables](COTEJO.md) · [Diseño e implementación por etapas](SOLUCION.md) · [Casos de aceptación](PRUEBAS.md) · [Evidencia ejecutada](probe-ia-actual-y-fuentes.json).

Preferencias del usuario: decisiones por tipos de hechizo y capacidades, actuación individual/equipo, buscar espalda y aprovechar elevaciones. Auditoría, especificación e implementación en curso; ver evidencia abajo. Dependencias: motor común de hechizos de la otra sesión, 0 (rendimiento), 14/15/29 (combates compartidos/instancias), E01 (configuración y recuperación).

## Plan ampliado

[Diferencias y portabilidad por subsistema](DIFERENCIAS-Y-PORTABILIDAD.md) · [Contratos, algoritmo y evaluación táctica](CONTRATOS-Y-ALGORITMO.md) · [Etapas, archivos y aceptación](PLAN-DE-IMPLEMENTACION.md).

## Prioridad y decisiones

**Prioridad 6 en el índice general**, condicionada a autoridad NPC/preview del motor común y medición de rendimiento. No requiere decisiones adicionales del usuario para avanzar. [Pendientes técnicos y alcance acordado](FALTANTES.md).

## Antecedente desplegado: servicio y puente v2 — 2026-10-06

Motor táctico v2 implementado en `server/ai-service`, sin Laya. Integración
acotada: módulos nuevos `combat_tactical_ai.py`, `combat_npc_spell.py`,
`combat_ai_capabilities.py`, `combat_ai_policy.py`, migración de perfiles y sustitución
únicamente de `pass_test_monster_turn`. Previews aislados, repertorio/nivel
propios, costes/rango/LOS/límites nativos y dispatcher común; primera acción
revalidada, commit atómico, entrega FIFO y redecisión. `13510` conserva la barrera
de fin de turno; no se inventa ACK por ataque. Foco de equipo solo tras commit.

Wonejo verificado; efectos obligatorios sin soporte se excluyen. Ataques nuevos
entran por consecuencias/previews y métricas versionadas sin whitelist en IA.
Cliente y handlers de hechizos comunes intactos. Puente inicial activo en
world tras reinicio solicitado el 2026-10-06, con health verificado. Ampliación
posterior activada el 2026-10-07: capacidades combinables, candidatos
intercalados, flancos y perfiles DB. Imagen acotada a IA, ai/world saludables;
30 pruebas sobre esa imagen y aceptación HTTP verificadas. Usuario confirmó
Wonejo atacando y jalató acercándose; ambos combates finalizaron según logs.
25 pruebas del servicio, con corpus ampliado. Pendientes roles nativos avanzados,
GUI/observadores completa y previsión de amenazas rivales. E18 continúa en implementación, no cerrado.

Contrato y extensión: [README del servicio](../../../server/ai-service/README.md).
Evidencia: [VALIDACION](../../../server/ai-service/docs/VALIDACION.md).
Prueba general: [PRUEBA-WORLD](../../../server/ai-service/docs/PRUEBA-WORLD.md).

### Lectura íntegra concurrente — revisión posterior aún sin desplegar

`ContextStore.read` verificaba primero con `has` y luego volvía a leer/hash
los mismos bytes, reteniendo el bloqueo global de uploads durante ambas
lecturas. Ahora lee una vez y verifica el SHA de todos los bytes exactos que
retorna. La publicación sigue siendo atómica; falta, directorio, hash inválido
y corrupción se rechazan. No hay cache de verificación ni datos omitidos.
Dos regresiones comprueban hash único/lecturas concurrentes y corrupción
posterior, además de rutas inválidas. **50 pruebas dirigidas OK**,40,889s:
`test_context_store test_context_snapshot test_bridge_context test_http`.
SDK completo copiado al entorno congelado para suite400. Pendientes esa suite,
despliegue solo AI y ensayo nativo completo. Imagen desplegada aún24e30,
world1ed06 mismo inicio14:53:48Z, reinicios propios1/3.

Validación posterior bajo entorno restringido: se añadió una regresión de
reemplazo atómico durante lectura. La copia de bytes ya leída se acepta solo
si coincide con el digest solicitado; una corrupción posterior se rechaza en
la siguiente lectura. **28 pruebas de almacenamiento/snapshots OK**,0,355s.
Este test adicional solo está en host; no se copió sobre la suite400 en curso.
Suite original10435 finalizada: **400 pruebas, una falla de expectativa de
mensaje y cero errores** (163,226s). La corrupción fue rechazada correctamente;
el test esperaba `Missing verified context content` en lugar de
`Context content changed while reading`. La expectativa está corregida en host.
Los manifiestos before/after coinciden: 1.405 registros sin cambios y 169 imports
nativos exclusivamente del snapshot congelado.
La corrida dirigida posterior ejecutó **48 pruebas, un error de permisos al
abrir el servidor HTTP local** (141,775s); no hubo fallas de assertions.
El sandbox ahora deniega `ps` y acceso al socket Docker de OrbStack; no se
pudo inspeccionar/desplegar AI ni ejecutar otro banco HTTP. Última imagen
verificada24e30, world1ed06/inicio14:53:48Z; no hay reinicios propios nuevos.
El acceso a Docker volvió a comprobarse tras el aviso del usuario y sigue
denegado por esta sesión; no se desplegó ni reinició ningún servicio.
Pendientes incorporar la regresión adicional y validar revisión
completa, despliegue soloAI y ensayo concurrente cuando Docker sea accesible.

Permisos actualizados: Docker accesible de nuevo. Inspección confirma las mismas
imágenes e inicios de AI/world indicados arriba; no hubo reinicio. Suite nueva
sobre el SDK completo actualizado en curso, log
`.runtime/local/e18-ai-host-sdk-corrected-frozen-suite.log`. Pendiente resultado
antes de desplegar la lectura concurrente íntegra.

La corrida delegada terminó con392 pruebas,26 errores de `socket.bind` por
permisos y0 fallas de assertions; manifiestos antes/después idénticos. No acredita
validación verde. La misma suite completa, incluyendo HTTP, está ejecutándose
en la sesión principal con acceso restablecido; log
`.runtime/local/e18-ai-host-sdk-corrected-frozen-suite-root.log`. Fuentes
congeladas sin cambios: AI85 SHA `badf4d464347019a5d04ca61203d956482dfec6bb6b7a5749e9936d011fc197c`.

### Revisión de lectura concurrente desplegada — 2026-10-07 16:55 UTC

Suite principal38561 **terminal0:401 pruebas OK**,90,884s de validación;
0 fallas,0 errores,0 omitidas.169 imports nativos desde el snapshot congelado;
1.405 registros antes/después idénticos, SHA
`df5ce95795b64e07c071cc890e66029017ce5af8191a1c12485bd86d160c0b88`.
Build95740 terminal0 usando el catálogo íntegro de la imagen viva de world.
AI desplegado `475f9668e0ee`, saludable, inicio16:55:51Z. World `1ed06b10b4d2`
saludable y mismo inicio14:53:48Z; reinicios propios **1/3**.
Ensayo14 turnos nativos en curso, handle8740, artefactos
`.runtime/local/e18-native-concurrent-read-turns.json` y `.log`.
La aceptación concurrente sigue pendiente hasta observar su resultado.

Revisión posterior en host, sin desplegar: publicación de uploads/imports
serializada por digest; bloqueo global solo para registro/metadata. SHA completo,
publicación atómica, offsets/retries y validación de corrupción conservados.
Locks de publicación con referencias débiles; callers retienen referencia fuerte
antes de esperar.30 pruebas almacenamiento/snapshots OK (0,221s), incluyendo
uploads/imports de hashes distintos en paralelo y mismo hash serializado.
Pendiente revisión completa y suite nativa antes de desplegar. El ensayo8740
sigue usando SDK congelado anterior/AI475f, sin cambios durante su ejecución.
Progreso aproximado comunicado:85%; aceptación concurrente/manual pendientes.

Ensayo8740 terminal0:14 turnos **adyacentes**, posición NPC[-7,-7,-1].
Ataques2/2 individual,4/4 concurrencia2,2/8 concurrencia4; invariantes intactos.
No es comparación con banco91003, que empieza distante[-5,-7,-1] y requiere
acercarse. Corrida distante nueva en curso, artefacto
`.runtime/local/e18-native-concurrent-read-distant-turns.json` / `.log`,
para validar movimiento+ataque con la misma distancia del banco anterior.
No atribuir diferencias de estos escenarios a una mejora de rendimiento.

Ensayo distante78921 **terminal0**: NPC[-5,-7,-1],14 turnos, ataques2/2
individuales (movimiento+cast),0/4 concurrencia2 (4 movimientos),0/8
concurrencia4 (0 movimientos). Todas las invariantes pasan. No acredita
aceptación concurrente; lectura concurrente por sí sola no la resuelve.

Publicación por digest, aún sin desplegar:32 pruebas dirigidas OK (0,161s),
con recuperaciones ante fallo antes de replace y después de publicar; retries
reverifican todos los bytes y limpian metadata parcial al encontrar canonical
válido. Revisión independiente readonly no detectó inversión de locks ni race
por weakrefs bajo el contrato existente de close sin callers activos.
SDK íntegro actualizado en snapshot después del terminal78921; suite completa
29891 en curso, log `.runtime/local/e18-ai-per-digest-frozen-suite.log`.
Manifiesto before1.405 registros SHA
`42e71de793c75af831243f71cbfb41ab23cc980d8d36767e19a59292c5122061`.
No desplegar ni modificar este snapshot hasta terminar la validación.

Revisión posterior sin desplegar: orden inicial de candidatos por rangos del
catálogo completo (baseline y todas las condiciones conocidas). Si todos los
primeros blancos están fuera de esos rangos, un movimiento se explora primero.
Metadata desconocida/incompleta, target propio o algún rango posible conservan
cast-first. No evalúa criterios ni valida legalidad: todos los casts/celdas y
movimientos permanecen en el conjunto de candidatos y pasan por native preview.
6 regresiones sintéticas OK (0,003s): rango/condicional/self/metadata futura,
roles distintos y paridad del conjunto completo de acciones. Prueba dirigida
nativa90935 en curso, log `.runtime/local/e18-native-range-order-focused.log`.
SDK frozen e imagen3a2 todavía sin esta revisión; pendiente suite completa y
despliegue soloAI antes de medir impacto en14 turnos distantes.

Suite65346 terminal1:411 pruebas, una falla de expectativa en corpus damage/heal,
0 errores/0 skips;95,187s y169 imports congelados, manifiestos idénticos.
El escenario de heal usaba XY0 a otra altura y esperaba movimiento antes de cast,
contradiciendo la ordenación conservadora recién añadida. Se corrigió el corpus
para usar ambos targets fuera de rango sin XY0.6 regresiones sintéticas OK
(0,003s). Nueva suite completa sobre SDK actualizado en curso:
`.runtime/local/e18-ai-range-order-corrected-frozen-suite.log`.
No hay despliegue de esta revisión todavía; AI activo sigue3a2bd.

Ensayo83433 terminal0:14 turnos distantes, ataques2/2 individual,0/4 y0/8
concurrencia2/4; movimientos2/2,3/4,2/8. Invariantes intactos. Todavía no
cumple aceptación concurrente. Próxima revisión en preparación, sin desplegar:
encoder directo para tuplas de enteros exactos antes de crear diccionarios
por scalar. Debe emitir bytes idénticos, reservar IDs antes de optimizar y
mantener fallback íntegro para bool/subclases/mixtas/futuros campos; verificación
cooperativa durante escaneo, antes de hash/cache. No se amplían plazos ni se
reducen contexto/legality. No hubo reinicio world; propio1/3.

Fast tuple encoder en host sin desplegar:42 pruebas contexto/geometría OK
(0,780s), con hash custom que lanza y subclase con fields futuros/ciclo.
Comparación alternada86474 terminal0 sobre50.000 tuplas ygrafo completo de
3.930.179 bytes:SHA idéntico `ca6d64827862a0608c1b5c6ed9dfa4fea90e38444bd756c63642a2dd621bb7d4`;
medianas0,237133s anterior y0,110784s actual. No es latencia de combate.
Artefacto `.runtime/local/e18-fast-tuple-controlled.json`, hashes de fuentes
registrados antes de actualizar snapshot. SDK íntegro copiado después de cerrar
bench/micro; suite completa en curso, `.runtime/local/e18-ai-fast-tuple-frozen-suite.log`.
Pendiente validar/manifiestos, deploy soloAI y14 turnos distantes.

Diagnóstico88172 terminal0 con motor anterior1ed06/AIbe646: ataques1/2,0/4,0/8;
invariantes intactos, no acredita jugabilidad live1c3bbe. Copia íntegra de
`/native/server` desde AIbe646:352 módulos nativos,439 tests nativos,76 SDKpy.
El empaquetado excluía tests/docs del SDK y heredaba pruebas antiguas del /app
original de world. Los46 módulos de ejecución sí coinciden por SHA con host.
Se eliminaron únicamente esas dos exclusiones de `.dockerignore` en AI; todavía
sin rebuild de empaquetado. Credenciales/caches/logs siguen excluidos.
La suite de esa copia parcial75721 terminal1:234 pruebas,5 fallas/9 errores,
168 imports congelados y manifiestos estables; no valida el SDK actual completo.
Después del terminal se copió TODO el SDK host85py sobre el motor nuevo1c3bbe,
sin modificar motor/tests nativos. Suite completa52831 en curso:
`.runtime/local/e18-ai-fast-tuple-live-complete-frozen-suite.log`.
Before1.851 registros SHA `56cdc021e7c7a9713012b05de95767341f80ce9c83ed5f3d1badb974c9c98462`.
Pendientes resultado/manifiestos, rebuild soloAI para incluirSDK completo y
14 turnos con motor actual. Reinicios propios1/3, world sin cambios propios.

Suite completa52831 terminal1 sobre motor1c3bbe y SDK85:415 pruebas,0 fallas
de assertions,1 error de importación del fixture nativo `test_combat_state_child_removal` desde
`tests.test_combat_timed_expiration`;134,076s,168 imports nativos congelados.
Manifiestos1851 idénticos, SHA `56cdc021e7c7a9713012b05de95767341f80ce9c83ed5f3d1badb974c9c98462`.
Runner ajustado para incluir directorio de fixtures `frozen/tests` en sys.path,
sin cambiar motor ni pruebas. Suite completa nueva en curso:
`.runtime/local/e18-ai-fast-tuple-live-fixtures-frozen-suite.log`.
No se omitió la prueba ni se tomó el error de harness como validación verde.


## Estado registrado antes del cierre de preparación del catálogo

# E18 — Motor de IA táctica de enemigos

## Estado actual — 2026-10-07

**Avance aproximado: 85 %.** Faltan aceptación manual del primer turno,
ataques consistentes bajo concurrencia y activar/validar el lector fragmentado.

**En implementación. Prueba manual del usuario detectó primer Wonejo sin actuar por timeout; aceptación real pendiente.**

| Componente | Estado verificado |
| --- | --- |
| World | `4b1bf7092447`, actualizado externamente; inicio `2026-10-07T19:09:09.655532553Z` |
| AI | `4e85a6edff16`, en ejecución; inicio `2026-10-07T19:18:06.065156318Z` |
| Suite AI e integración nativa | **437 pruebas OK sobre el motor anterior `bcfd5fe73cd8`**; suite actual:440 pruebas OK (157,822s),169 imports nativos sin externos |
| Código empaquetado |SDK completo reconstruido con el motor vivo; encoder experimental sin activar |
| Reinicios propios de world | **1/3**; ninguno nuevo en estas iteraciones |

World cambió externamente durante la validación del prototipo. Copia completa
del nuevo motor: 352 archivos Python nativos y 441 de tests. SDK 87 archivos
Python. Suite del motor nuevo **57756 terminada exit0**: 433 pruebas,
140,853 s de validación; 169 imports nativos, ninguno externo. AI reconstruido
con ese catálogo; build **17424 terminado exit0**. Ensayo **74796 terminado exit0**: con el presupuesto anterior de 5 s,
ataques 2/2 individuales, 1/4 con concurrencia 2 y 0/8 con concurrencia 4;
invariantes sin fallos. La tabla siguiente conserva el ensayo previo.

Por instrucción del usuario, el presupuesto predeterminado pasa a **10 s por
turno completo de IA**. Cambio limitado al SDK; carga automática sin reiniciar
world. 21 pruebas de turno, entrada y loader OK (0,079 s). AI reconstruido (93822 exit0), sin reiniciar world. Verificación dentro de
world: SDK cargado con presupuesto 10 s; la política SQL activa `normal:1`
no sobrescribe `turnMs`. Ensayo con 10 s (77528): terminado exit0.
Ataques **2/2 individuales, 4/4 con dos encuentros y 6/8 con cuatro**.
Todas las invariantes pasan; aceptación concurrente completa pendiente.
Tiempos: individual 9,352–9,578 s; concurrencia 2: 9,410–9,779 s;
concurrencia 4: 5,024–10,320 s. El cierre cooperativo puede exceder unas
décimas el presupuesto, por lo que no se afirma un límite duro de 10 s.
Evidencia: `.runtime/local/e18-ten-second-budget-tests.log`,
`.runtime/local/e18-ten-second-ai-rebuild.log` y
`.runtime/local/e18-native-ten-second-bcfd-live-turns.log`.

Procesos 50147 (suite previa), 33045 (build previo solo AI) y 2244 (ensayo previo)
terminaron exit0.
Evidencia:

- `.runtime/local/e18-ai-direct-instance-new-world-full-suite.log` (433 pruebas, motor actual).
- `.runtime/local/e18-native-direct-instance-bcfd-live-turns.log` (ensayo actual en curso).
- `.runtime/local/e18-ai-direct-instance-deadline-full-suite.log` (revisión anterior).
- `.runtime/local/e18-ai-direct-instance-rebuild.log`.
- `.runtime/local/e18-native-direct-instance-live-turns.json`.

El ensayo anterior usa el motor `1c3bbe`, mapa completo de 7.075 celdas y
24.556 aristas, encuentros privados independientes y transporte HTTP real.
No modifica combates reales ni acredita por sí solo el ACK del cliente.

| Encuentros simultáneos | Ataques | Turnos medidos | Tiempo observado |
| --- | --- | --- | --- |
|1|2|2|5,254–5,411s|
|2|0|4|4,548–4,686s|
|4|0|8|3,740–5,244s|

Las invariantes comprobadas pasan en los 14 turnos. Persisten agotamientos
del plazo; **no se acredita aceptación concurrente ni un SLA**.
El registro de revisiones y fallos anteriores se conserva en
[historial de validación](HISTORIAL-VALIDACION-HASTA-20261007.md).

## Alcance y reglas vigentes

- Todo cambio de lógica se hace en `server/ai-service`; documentación E18
  y artefactos de validación también están autorizados.
- Puente genérico v3 ya integrado una vez: no añadir campos o lógica a world
  para cada hechizo. El SDK completo se monta read-only y mantiene las
  consultas/ejecuciones en el hilo propietario del combate.
- Server entrega **todo** el contexto, fuentes, catálogos, autoridades y
  campos futuros. No hay recortes de monstruos, habilidades, mapas o datos
  para ajustar el tamaño de un paquete.
- **Arquetipos y capacidades genéricos**. Ninguna regla por nombre o ID de
  monstruo. Solo mecánicas explícitas de tipo puzzle admiten excepciones.
- Una sola versión activa de AI; reinicios de AI autorizados. Dockerfile
  conserva `COPY .`, con el catálogo completo de la imagen viva de world.
- Cliente, porcentajes de drop y checkpoint de persistencia quedan fuera
  de este trabajo. Preservar los cambios de los agentes de world.
- Máximo 3 reinicios propios de world en total, avisando antes. El tercero
  cierra también la autorización para seguir editando archivos.

## Implementado y comprobado

El servicio genera candidatos y compara resultados de previews nativos:
movimiento, lanzamiento, soporte, control, orientación y coordinación.
No replica fórmulas de daño ni inventa legalidad. Conserva alternativas y
replanifica tras cada acción ejecutada; los planes no son órdenes ciegas.
Los perfiles y capacidades permiten combinar afinidades, sin encerrarlas
en una sola etiqueta ni construir árboles por especie.

El puente conserva runtime y actores completos, builds/decks, invocaciones,
fuentes de autoridad, topología XYZ dirigida y callbacks como descriptores.
La ejecución nativa conserva FIFO y la barrera real de ACK. Los snapshots
privados, checksum, alias y ciclos se verifican; una dependencia obligatoria
no soportada se declara explícitamente.

Últimas correcciones:

- Build predeterminada 0 sin fila SQL: el adaptador usa `catalog_indices` y
  `default_deck` nativos, sin fabricar registros. Verificado read-only con
  el personaje real 10: build 0, filas guardadas [], catálogo [0], deck 24 bytes.
- Encoder y cachés de geometría conservan bytes completos y distinguen
  objetos iguales con identidades diferentes. Los campos futuros hacen
  usar el camino completo cuando no son elegibles para un cache.
- Publicación de snapshots comprimidos directamente por bloques: elimina
  la consulta previa redundante. Duplicados conservan el archivo verificado,
  corrupción se repara con checksum completo y ACK perdido se reintenta.
  El deadline se comprueba antes/después de comprimir.

## Diagnóstico del Mimic reportado

Combate 23: Mimic HP 1, PA 0, PM 3, WP 0, posición `[-23,16,-8]`; rival
`[-23,17,-9]`. Ya estaban adyacentes. Los cinco Mimics del catálogo vivo
conservan `native_abilities=[]`. Los dos movimientos comparados gastan 2 PM
sin reducir distancia:score −0,2 frente a 0 por pasar.

Antes, el rechazo de la build 0 impedía siquiera buscar; eso está corregido.
La ausencia de ataques y la lentitud de consultas son problemas distintos.
No se inventará un ataque ni una regla de huida del Mimic. Una conducta de
retirada deberá proceder de un arquetipo/capacidad y utilidad genéricos.

## Próximo trabajo

El prototipo de [grafo por fragmentos](../../../server/ai-service/docs/FORMATO-GRAFO-FRAGMENTADO.md)
ya supera **14 pruebas de formato** y reconstruye exactamente los 73.677 nodos de
la geometría real del mapa 1134, con todos sus bytes y alias. No está activado:
partir de un grafo plano y reconstruirlo todavía cuesta demasiado. Encoder directo experimental implementado; falta conectar el lector virtual
y el transporte con fragmentos verificados.

1. Reducir el coste de serializar/leer geometría completa repetida mediante
   fragmentos inmutables y verificables, conservando **todos** los nodos,
   campos, referencias y alias. Validar el formato antes de activarlo.
2. Acreditar ataques y finalización de turno con encuentros simultáneos,
   sin consumir más reinicios de world ni recortar contexto.
3. Ampliar arquetipos derivados y combinaciones de capacidades con fixtures
   del motor nativo; incorporar hechizos nuevos automáticamente cuando el
   motor común los implemente. Mecánicas puzzle deben ser explícitas.
4. Ejecutar una partida manual completa: acercamiento, ataque, muerte de
   un enemigo, resultados y un segundo encuentro sin memoria obsoleta.

## Prueba manual general

En Amakna, mapa 1134, instancia 0:

1. Escribir `!pos` y comprobar mapa/instancia.
2. Escribir `!mob 5525 1 2`, atacar al grupo de dos Wonejos de nivel 1,
   colocar el personaje a varias celdas y marcar Listo.
3. Pasar varios turnos: deben moverse por celdas libres con PM descontados
   y atacar cuando su habilidad nativa tenga un blanco legal.
4. Adyacente a un Wonejo: como máximo un lanzamiento por turno sobre el
   mismo blanco, conforme a su límite nativo; sin daño o recursos gratis.
5. Derrotar a uno: el superviviente debe usar el roster actualizado.
6. Terminar la pelea, comprobar resultados y empezar otra: no debe
   arrastrar foco ni acciones del encuentro anterior.

Pasos y evidencia de FIFO/ACK en la
[prueba completa de world](../../../server/ai-service/docs/PRUEBA-WORLD.md).
Los ataques aún no implementados por el motor común no se simulan desde AI.

## Diseño y evidencia

[Servicio](../../../server/ai-service/README.md) ·
[Validación](../../../server/ai-service/docs/VALIDACION.md) ·
[Inventario del puente](../../../server/ai-service/docs/BRIDGE-INVENTORY.md) ·
[Catálogo Docker](../../../server/ai-service/docs/CATALOGO-CONTENEDOR.md) ·
[Pendientes](FALTANTES.md).

[Cotejo con Dofus sin Laya](COTEJO.md) · [Solución](SOLUCION.md) ·
[Contratos y algoritmo](CONTRATOS-Y-ALGORITMO.md) ·
[Etapas](PLAN-DE-IMPLEMENTACION.md) · [Casos de aceptación](PRUEBAS.md).

Prioridad 6 del índice general; dependencias: motor común de hechizos,
rendimiento 0, combate compartido/instancias 14/15/29 y configuración E01.

Avance del encoder directo: `GeometryFragment.identity_map` y
`fragment_descriptor` asignan todas las referencias sin renderizar nodos
globales; raíz reservada y alias externos conservados. 35 pruebas dirigidas
OK (0,793 s). Formato experimental todavía sin activar; siguiente paso es
provisionar los blobs completos y conectar el lector virtual. Evidencia:
`.runtime/local/e18-direct-fragment-identity-tests.log`.

Encoder directo experimental implementado: `encode_parts` conserva el
orden DFS y provisiona blobs locales completos; caché de 32 fragmentos
inmutables (solo caché, sin límite al contexto). Los mapas globales se generan
de nuevo por snapshot. 37 pruebas dirigidas OK (0,845 s), con roundtrip
exacto, alias exteriores, raíces reservadas, ciclos, campos futuros y reutilización
del blob sin renderizar nodos. Todavía no está activado en el transporte.
Suite93218: **435 pruebas OK**, 162,352 s; 169 imports nativos del motor
actual, ninguno externo. Resultados escritos, proceso cerrándose. Corresponde
a la revisión previa al encoder directo; no se atribuye a cambios posteriores.

## Fallo real comunicado por el usuario — 2026-10-07

Combate30, turno1: primer Wonejo pasó por `native_ai_query_or_commit_rejected`,
`Native AI turn deadline reached`. El segundo movió; turnos posteriores
registran movimientos y un cast7962 (turno9). No acredita aceptación manual.
World cambió externamente a `4b1bf7092447`, inicio19:09:09Z; AI todavía
se basaba en bcfd al ocurrir el fallo. Se sincroniza AI con imagen actual.

El ensayo anterior calentaba motor y catálogo antes del reloj; se añade
`benchmark_native_concurrent.py --cold` para incluir preparación/provisión
en el primer turno medido. No se asume que el timeout haya ocurrido en
catálogo: ahora el diagnóstico registra etapa y tiempo transcurrido.
51 pruebas dirigidas OK, 0,824 s; suite anterior437 OK,111,492 s,
169 imports del motor bcfd, ninguno externo (30265 exit0), sin atribuirla
al motor nuevo ni a cambios posteriores.

Sincronización39050 terminó exit0; AI `4e85a6edff16` con world
`4b1bf7092447`. Prueba fría de dos turnos en curso85875, sin prewarm ni
provisión anticipada. World no se reinició; contador propio1/3 intacto.

Provisión del world vivo72443 exit0:13.302 entradas,712.668.863 bytes,
seal completo sin faltantes. Se automatiza en `rebuild.sh`;3 pruebas
de no modificar world, rechazo de cambio de imagen y seal incompleto OK.

Ensayo92470 sin prewarm nativo:0/2 ataques,10,356–23,789s; no reproduce
la precarga que world hace antes de abrir listeners. Nuevo ensayo3476
usa `--cold-catalog`, conserva esa precarga nativa e incluye la preparación
del catálogo dentro del turno. Pendiente resultado; no se declara arreglado
el fallo manual.

Ensayo3476 (`--cold-catalog`, motor prewarm como en arranque world)
terminado exit0: **2/2 turnos con movimiento y ataque7962**, daño5 en ambos,
sin fallback ni fallos de invariantes. Tiempos9,209–9,693s; preparación
de catálogo primera4,630s, segunda inferior. Evidencia:
`.runtime/local/e18-native-cold-catalog-owner-world-live-turns.json`.
Se pidió repetir pelea nueva y comprobar primer Wonejo; aceptación manual
todavía pendiente. No reinició world.

Provisión de catálogo: revisión Luna añade regresiones de cambio de world
tras seal, fallo de copia y JSON malformado; **7 pruebas OK**,0,017s.
Suite actual6707 sigue ejecutándose; no se declara resultado final todavía.

Lector virtual implementado e integrado de forma **opt-in**; no activo en
peleas reales. Encoder, lector y transporte HTTP conservan todos los bytes
y referencias. Prueba HTTP de provisión, corrupción con caché caliente y
reparación íntegra OK (31 pruebas context/format/HTTP,0,560s tras corregir
importio). Suite completa de esta revisión en curso.

Prueba de codec con mapa1134 completo:7.075celdas,24.556aristas,73.677nodos,
4.991.776bytes; roundtrip exacto. Manifest73.221bytes gzip y2blobs completos
5.454.506bytes. Encoder frío1,361s/caliente0,050s; lector frío0,755s/caliente
0,439s. Solo codec, no SLA ni prueba de turno real. Evidencia:
`.runtime/local/e18-native-direct-parts-real-arena-probe.json`.

Instrucción vigente del usuario: avanzar mientras aporte al sistema general
y detenerse cuando el siguiente progreso útil dependa de hechizos ausentes.
No se declaran implementados ataques que el motor nativo no tiene.

Lector fragmentado:20 pruebas de formato OK contra motor4b1,0,029s
(confirmación root de casos nuevos de Luna). Corrupción tras cache caliente,
JSON duplicado/no canónico, mapas bool/duplicados/fuera de rango y campos
futuros dinámicos comprobados. Transporte continúa desactivado por defecto;
suite opt-in8484 sigue ejecutándose.

