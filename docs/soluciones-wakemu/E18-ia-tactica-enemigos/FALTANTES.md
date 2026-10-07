# Pendientes y decisiones — E18

Estado y evidencias actuales: [README](README.md).

## Pendientes actuales

1. Confirmar una pelea completa nueva, especialmente el primer Wonejo.
2. Mejorar/validar aceptación concurrente con cuatro encuentros: la fracción
   productiva 0,25 logró 6/8 ataques y 8/8 movimientos; ninguna invariante falló.
3. Mantener como referencia la suite final: 459 pruebas OK sobre la imagen
   actual `3af10843cbc6`, 169 imports nativos y ninguno externo.
4. Cuando existan más hechizos nativos, validar roles mixtos y balance de
   perfiles con esos efectos reales. El repertorio se descubre automáticamente;
   no se requieren ramas por monstruo ni cambios nuevos en el puente.
5. Mantener pendiente el coste completo bajo carga y la aceptación en cliente;
   el banco de encuentros privados no acredita FIFO/animaciones reales.

## Decisiones actuales

- Lógica solo en `server/ai-service`; no modificar cliente ni fuentes de world.
- Contexto completo, sin filtrar catálogos ni campos futuros.
- Arquetipos/capacidades genéricos; excepciones únicamente para puzzles explícitos.
- Presupuesto de turno 10 s y una única versión de AI.
- Formato fragmentado desactivado tras empeorar la medición nativa.
- Detener las extensiones especulativas cuando su validación dependa de los
  hechizos pendientes, conforme a la instrucción del usuario. E18 no está completo.
- Reinicios propios de world: 1/3, ninguno nuevo; avisar antes de otro.

## Antecedentes históricos

Los apartados siguientes pertenecen a revisiones anteriores; sus tareas no
reemplazan la lista actual.

# Pendientes y decisiones — E18

Estado actual — 2026-10-07: world `4b1bf7092447`, inicio externo19:09:09Z;
AI `4e85a6edff16`, inicio19:18:06Z. Reinicios propios world1/3 intactos.
Prueba manual del usuario NO aceptada: primer Wonejo pasó por timeout.
Reproducción fría85875: el primer turno agotó10s preparando catálogo;
ninguna búsqueda iniciada. Se provisionó la copia completa del world vivo
(13.302 entradas,712.668.863 bytes), seal completo sin faltantes.
`rebuild.sh` ahora provisiona y sella esa copia antes de dar AI por listo;
3 pruebas de esa operación OK. No cambia ni reinicia world.

Nuevo ensayo3476 en contenedor world: catálogo frío, motor prewarm como
en el arranque real del servidor. Pendiente resultado. Ensayo92470 sin
prewarm de motor falló también, incluida carga nativa síncrona23,8s; ese
proceso aislado no reproduce el motor ya calentado antes de listeners.
Suite437 OK sobre bcfd anterior (30265 exit0), sin atribuirla al motor nuevo
o cambios posteriores;51 pruebas dirigidas SDK OK. Encoder fragmentado
experimental sin activar; todavía falta lector e integración.

Los estados de otras imágenes que siguen son antecedentes históricos.


Estado verificado 2026-10-07: AI `50a9e3303416`, saludable desde
18:22:21 UTC; world `1c3bbea57e40`, saludable, conserva inicio 17:23:41 UTC.
Reinicios propios de world **1/3**, ninguno nuevo. Suite final50147:
**422 pruebas OK**, 104,535 s; 169 imports del motor vivo congelado,
ninguno externo. Build33045 y ensayo2244 terminal0, solo AI reiniciado.
85 archivos Python de la revisión desplegada verificados por SHA al desplegar.

Envío directo de snapshots completos por bloques desplegado; checksum íntegro,
idempotencia y reparación de corrupción, con checks antes/después de comprimir.
Ensayo:2/2 ataques individuales,0/4 con concurrencia2,0/8 con concurrencia4;
invariantes íntegros, aceptación concurrente todavía pendiente.
`.runtime/local/e18-native-direct-instance-live-turns.json`.

Prototipo no activado `native_graph_parts.py`:11 pruebas puras OK contra el
motor actual. Roundtrip exacto de la geometría real de Amakna1134:
73.677 nodos, 4.991.776 bytes, sin perder alias ni campos. Manifest posterior
73.177 bytes gzip; los dos blobs completos se provisionan antes. El lector
actual reconstruye todo y sigue siendo lento; falta encoder directo y lector
virtual antes de integrar/desplegar. Ver FORMATO-GRAFO-FRAGMENTADO.md.

Política: arquetipos/capacidades genéricos; excepciones solo para puzzles
explícitos. Nada nuevo en world ni cliente. Los datos de revisiones anteriores
que siguen son antecedentes, no describen esta versión.


## Información necesaria del usuario

**Ninguna decisión bloqueante por ahora.** El alcance ya está definido: IA táctica individual y de equipo, reutilización de Dofus sin Laya, espalda/lateral y elevaciones, reglas/configuración en DB y cambios solo del servidor.

Base propuesta para implementación: selector determinista por capacidades y previews; primeras pruebas con repertorios que el motor ya ejecuta. No exigir una lista manual de habilidades, fórmulas, roles ni mapas al usuario: deben extraerse/cotejarse en código y catálogos.

El balance final (agresividad, coordinación y dificultad) se evaluará con perfiles parametrizados y resultados de pruebas; no hace falta fijarlo antes de construir el motor. Si el usuario tiene preferencias adicionales podrán incorporarse, sin bloquear investigación o implementación autorizada.

## Trabajo técnico pendiente

Estado histórico de la revisión anterior: AI `ff966ee791c1`, saludable desde
18:09:18Z; world `1c3bbea57e40`, saludable, conserva inicio17:23:41Z.
Reinicios propios **1/3**, ninguno nuevo. Build46349 terminal0, solo AI;85 archivosPython íntegros porSHA.
**419 pruebas OK**, 109,737s;169 imports exclusivamente del motor vivo
congelado1c3bbe, sin imports externos. Log:
`.runtime/local/e18-ai-leaf-seeding-full-suite.log`.
Build predeterminada cero sin fila SQL corregida en el adaptador del SDK,
sin inventar registros ni cambiar world. El Mimic continúa pendiente por
plazos agotados o movimientos sin ventaja, no por ausencia de PM.
Política: **arquetipos/capacidades genéricos; ninguna regla por monstruo**,
excepto mecánicas explícitas de tipo puzzle. Ensayo14turnos con motor1c3bbe
actual terminal0: `.runtime/local/e18-native-build-zero-live-turns.json`.
Resultados:2/2 ataques individuales,0/4 con concurrencia2,0/8 con
concurrencia4; invariantes íntegros. La aceptación concurrente aún falla.
Aceptación concurrente y manual integral pendientes. Las cifras posteriores
son evidencia histórica cuando indican otra revisión.


Medición de revisión anterior24e30: banco91003 **2/2 ataques individuales**,
**1/4 con concurrencia2**, **0/8 con concurrencia4**, invariantes íntegros.
Artefacto `.runtime/local/e18-native-relative-inventory-turns.json`.
La nueva medición debe determinar si la lectura concurrente mejora este límite;
no asumirlo por la reducción de trabajo local ni por las pruebas verdes.

Las mediciones siguientes son históricas y no describen la revisión actual.

Estado histórico verificado: AI `befd1af16751`, saludable; world `1ed06b10b4d2`
saludable, inicio `2026-10-07T14:18:11.366599745Z`, reinicios propios **1/3**.
World actualizado por otra sesión; puente/volumen intactos. Observación
posterior: misma imagen, reinicio externo a las14:53:48Z; propio1/3.
Build97636 terminal0: AI `befd1af16751`, saludable, inicio14:58:48Z.
Suite combinada actual:381 OK /147,864s; hashes de AI y retained estables,
el manifiesto general de world cambió por trabajo externo. Fragmentos íntegros de
geometría desplegados. Banco11476 terminal0, motor/SDK congelados;
`.runtime/local/e18-native-geometry-fragment-turns.json`:1/2 ataques individuales,
0/12 concurrentes, invariantes intactos. Sigue pendiente aceptación
concurrente y perfil de preparación/verificación del turno completo.
Las mediciones siguientes describen las versiones anteriores. Build38744
terminal0; build posterior30067 terminal0, AIinicio14:29:33Z. Suite363 OK /98,810s y hash AI
estable;49 dirigidas después del encoder reutilizado OK /0,407s. Extensión
de utilidad v3 conectada con provider privado puro y pesos explícitos;
mediciones ausentes desconocidas. Cache de adyacencia nativa y driver de
commit inmediato con guard desplegados. Banco74685 terminal137 durante
prewarm/cambio de world, sin resultado válido. Copia completa de `/app` de
imagen actual en `.runtime/e18-world-native-1ed06b10b4d2`; banco74384 terminal0
en host contra ese mismoAI, salida
`.runtime/local/e18-native-extended-handoff-host-turns.json`.
Resultado0/14 ataques, movimientos1/2,4/4,2/8 e invariantes intactos.
Ataque seleccionado en primer individual venció antes del commit; segundo
individual cerró sin expandir. Jugabilidad distante actual no acreditada.
Telemetría nueva del límite de corte pasa47 pruebas; build30067 desplegado.
Banco12850 terminal0 con SDK y motor copiados de la misma imagen: ataques
2/2 individuales,0/4 con concurrencia2 y0/8 con concurrencia4; invariantes
intactos. Artefacto `.runtime/local/e18-native-frozen-sdk-budget-evidence-turns.json`.
Los cortes observados proceden del plazo real, no del presupuesto local de
exploración. Pendiente integrar y verificar cache íntegra de fragmentos de
geometría, sin modificar world ni excluir nodos, referencias o campos.

Evidencia anterior:
Suite desplegada:332 pruebas OK /161,220s. Banco49663 terminal0 y artefacto
`.runtime/local/e18-native-frozen-delta-turns.json` recuperado: ataques2/2
individuales,0/4 con concurrencia2 y0/8 con concurrencia4. Todos los
invariantes pasan; con4 no llega ninguna búsqueda a AI y hay turnos de
67,93–93,69s. La observación registra swap y carga externa; hubo cambios
de catálogo durante el ensayo, por lo que no es comparación aislada de
rendimiento. Sigue pendiente la aceptación concurrente.

Desplegados: alternancia exhaustiva de hechizos y movimientos y agrupación
de inventarios anterior al escaneo. Ambos pasan50 pruebas dirigidas
/18,830s y batería341 OK /166,317s. La primera corrida75552 falló por
regresión nativa corregida por otra sesión; la repetición9590 tiene footer
verde pero el archivo nativo cambió de hash durante la corrida. No acredita
un checkout inmutable. Build15540 terminal0, AIhealthy; ensayo nativo actual
88495 contra motor de la imagen viva,14 turnos, salida
`/data/e18-native-batched-alternating-turns.json`. No se excluyen datos,
hechizos ni rutas; world no se cambió ni reinició.

Las entradas siguientes son evidencia histórica. Estado anterior: AI `c321f613a16d`, saludable; world `e839fd35a2c1`
sin reinicio propio adicional (**1/3**). Suite conjunta 321 pruebas OK.
Banco `.runtime/local/e18-native-sealed-context-turns.json`, sesión84576
terminal0: 0/14 ataques, un movimiento con dos turnos simultáneos, todos
los invariantes conservados. La copia completa del catálogo redujo su
verificación individual a 0,29–0,31 s. La decodificación diferida de
geometría agotó el límite de exploración antes de probar movimiento.
Corrección posterior en validación, aún sin desplegar: esa decodificación
cuenta como preparación íntegra, conservando BFS/ordenación/evaluación bajo
el presupuesto local y toda preparación bajo el plazo real. 25 pruebas
dirigidas OK. Las mediciones y versiones inferiores son evidencia histórica.

### Puente completo v3 — actualización 2026-10-07

Ya existen en `server/ai-service` el codec íntegro, catálogo provisionado
directamente en Docker, almacén verificado, oráculo actor-completo,
negociación HTTP, búsqueda por consultas y driver/commit nativos. Wonejo
en arena completa y commit PC tienen evidencia de prueba. Todavía falta:

- La previsión rival ya se conectó a la selección de planes v3 y pasó cinco
  pruebas de ranking. Completar su aceptación nativa y
  roles/posición con datos nativos y dependencias explícitas. El foco y
  su historial ya se confirman después de la publicación real en v3; faltan
  aceptación de corredores de tiro en juego, reservas de movimiento y
  preferencias avanzadas de apoyo. El SDK ya confirma reservas de probes LOS
  nativos después de publicar; no se acreditan casts futuros como comprometidos.
- Ensayo compartido HTTP completo:7075celdas/24556aristas, ataque7962
  comprometido a4,738s y cierre publicado a5,029s. Completar percentiles y
  concurrencia; el plazo es cooperativo y el fallback puede excederlo.
- Puente final ya desplegado en world `6319c87dedd6` (actualizado por otra sesión), SDK read-only y AI
  `ac8c8ca87419`, ambos saludables. World actual `e839fd35a2c1` fue desplegado
  por otra sesión y conserva puente/volumen. Cambió únicamente la función acordada del
  world vivo. Reinicios propios1/3; avisar antes de cada uno, después del
  tercero no hacer más cambios. No repetir parches de world para ampliar IA.
- Aceptación conectada al juego pendiente: ejecutar la partida completa de
  `server/ai-service/docs/PRUEBA-WORLD.md`; no afirmar que todo E18 esté completo.

Última suite conjunta AI y regresiones raíz:284 pruebas OK /48,250s
(48,860s totales; cero fallos, errores u omisiones).
Preview conserva recibo completo (tx+packets+acción+fuente) en grafo compartido;
runtimeIdentity separado deduplica búsqueda y pronóstico sin perder recibos.
La ampliación en código captura el contexto completo del callback nativo de
daño y diferencia localización observada de la aplicada por el efecto.
Pasaron 58 pruebas enfocadas y una prueba con el ataque nativo del Wonejo;
Suite de captura270 aprobada y desplegada. Medición HTTP anterior al ajuste de captura:
ataque4,274s/publicación5,276s,17 guards intactos,9 paquetes FIFO y evidencia
FRONT nativa. El ajuste posterior preserva el callback si falla la captura;
30 focales y suite completa posterior de270 aprobadas. Ampliación desplegada
exclusivamente en AI; health/loader aprobados, catálogo11048 entradas íntegro
verificado por rehash, ningún objeto faltante. World no fue reiniciado.
Después,49 focales OK /0,902s, incluyendo dos regresiones nuevas: coordenadas
corruptas y corredores con rayos nativos de Amakna.
El beam conserva diversidad intent/target; capacidades observadas ordenan
blancos sin excluirlos ni añadir bonus. Esto avanza los roles, pero no
acredita aún aceptación de corredores ni roles avanzados en juego.
El ajuste posterior de registro de bajas/curación pasó32 pruebas enfocadas.
Ampliación posterior de apoyo validada: rutas hacia aliados con déficit real
de HP y conservación de una rama que reduce distancia dirigidaXYZ, sin bonus
ni filtro.55 focales y suite276 aprobadas. Prueba de contrato con beam2:
curación fuera de raíz, legal tras escalera; sin curación no se premia la ruta.
NativeOracle real prueba rodeo+BACK por mayor daño y fuente intacta.
Desplegada en AI58413db8dc02; catálogo11048 entradas/689711986 bytes,
rehash completo sin objetos faltantes, health/loader aprobados. Ensayo HTTP
posterior:cast4,738s/cierre5,029s,15 guards intactos,9 paquetes FIFO.
Todavía faltan apertura
lateral de LOS sin acercarse y protección de aliados con HP lleno.
Contra la imagen viva antigua:22 pruebas de integración/loader/estadísticas
OK;16 pruebas nativeOracle/turn OK y la restante, corregida la ruta de un
auxiliar de tests, OK aislada. Mantener implementación, prueba y despliegue
como evidencias distintas.

### Pendientes generales del sistema

- Extensión de utilidad v3 conectada y desplegada. Falta aceptación ampliada
  con mecánicas nativas avanzadas ejecutables; no inferir utilidad de nombres
  de hechizos ni campos arbitrarios. Productores/adaptadores permanecen en AI.

Concurrencia medida contra servicio real:14 turnos, cohortes1/2/4 con2
repeticiones. La fuente/publicación/ACK quedó aislada, pero ataques1/2,0/4,0/8
y0 consultas en las cohortes4. No dar esa prueba por rendimiento aprobado.
Optimizaciones de preparación/inventario y hashing paralelo conservan datos
completos y pasaron suite284. AIac8c8ca87419 deployed/healthy, catálogo11050
entradas/689726240 bytes íntegro, sin faltantes. Medición posterior2/2 ataques
individuales,1/4 con2,0/8 con4;8 consultas iniciadas con4, sin fallos de
aislamiento/publicación/ACK. Rendimiento insuficiente: no dar E18 por completo.
Corpus pequeño: no acredita SLA. Ensayo movimiento+ataque distante en curso.

- Ampliar autoridad/adaptación NPC y preview desde el SDK de ai-service;
  no repetir parches externos ni cambiar archivos compartidos de world.
- Acreditar orientación final, topología/LOS de mapas seleccionados y callbacks/reacciones de rutas.
- Ejecutar corpus de roles, planes y coordinación con varios encuentros; medir presupuestos y latencia concurrente.
- Conectar `rivalForecasts` al productor nativo. El contrato/ranking ya tiene
  regresiones y aceptación HTTP, y el SDK carga autoridades propias de todos los PC
  del encuentro. Falta ampliar la aceptación nativa concurrente y de roles. La proyección necesita
  los datos reales del rival, movimiento PC y lifecycle completo en una copia
  privada de runtime (callbacks, expiración y comienzo del turno). Compartir
  presupuesto con previews NPC; no rellenar estados sin forecast con riesgo0.
- Verificar sincronización/GUI con personajes de prueba y observers; no pedir al usuario que sustituya estas pruebas por decisiones.

Son tareas técnicas del implementador. E18 sigue en implementación. El objetivo está activo; estos pendientes son trabajo técnico y no solicitudes de aprobación. Puente inicial activado; capacidades, flancos, perfiles DB y pruebas ampliadas se documentan en el README del servicio.


### Actualización de búsqueda — 2026-10-07

- AI b9acc96d742d desplegado, suite conjunta293 OK /90,323s.
- Presupuesto activo ya excluye espera de consultas; hint SDK conserva
  deadline real y reserva. El ensayo anterior aún dio solo1/2 movimientos
  y0/2 ataques (`e18-native-distant-budget-turns.json`).
- Scheduler quantum2 certificado por regresiones: tres consultas bastan
  para seleccionar move+cast en fixture; streams siguen completos.
- Pendiente diversidad global: beam por quantum y prioridad DFS pueden
  postergar ramas raíz bajo deadline.
- Ensayo real actual activo sesión84219; Docker también demora respuesta
  de consulta de procesos sesión34212. Sin terminal ni reinicio automático.
- No reutilizar planes comparando forecast runtime y commit: callbacks,
  serialización, entrega y RNG real pueden diferir. Necesita recibo esperado
  de commit completo, no eliminar campos de identidad.
- Reinicios propios world1/3; conservar límite y aviso antes de cada uno.


### Banco nativo corregido y estado desplegado — 2026-10-07

AI4aa49a03651c saludable, suite307/123,175s OK. Fixture ahora instala PV
variables antes del snapshot y valida características nativas de todos los
actores antes del turno. Banco14 turnos, sesión54895 terminal0,
`.runtime/local/e18-native-fair-concurrent-valid-turns.json`:0/14 ataques;
movimientos2/2,2/4,0/8; invariantes válidos pero táctica/rendimiento pendientes.
Verificar catálogo tarda2,8–3,2s con4 y el primer HTTP inicia4,1–4,5s.
Con1, tras mover, nueva sesión empieza4,3–4,5s y vence antes de atacar.
La búsqueda solo expande profundidad1 porque la decodificación completa
de la continuación consume el presupuesto activo. Medir/optimizar trabajo
duplicado antes de atribuir avance a un aumento arbitrario de plazos.
Worlde839fd35a2c1, inicio10:38:41Z,1/3 reinicios propios.

Ensayo3476 (`--cold-catalog`, motor prewarm como en arranque world)
terminado exit0: **2/2 turnos con movimiento y ataque7962**, daño5 en ambos,
sin fallback ni fallos de invariantes. Tiempos9,209–9,693s; preparación
de catálogo primera4,630s, segunda inferior. Evidencia:
`.runtime/local/e18-native-cold-catalog-owner-world-live-turns.json`.
Se pidió repetir pelea nueva y comprobar primer Wonejo; aceptación manual
todavía pendiente. No reinició world.
