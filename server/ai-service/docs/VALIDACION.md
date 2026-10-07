# Validación — E18

Estado actualizado y evidencia: [README de E18](../../../docs/soluciones-wakemu/E18-ia-tactica-enemigos/README.md).

World `3af10843cbc6`, AI `26576b10f2bb`. Sin reinicio nuevo de world;
contador propio **1/3**. Catálogo completo sellado: 13.269 entradas.
Suite final: **459 pruebas OK**, 115,552 s de tests/116,222 s de validación,
169 imports del motor actual congelado y ninguno externo. 60 focalizadas OK.
Evidencia: `.runtime/local/e18-ai-package-layout-final-full-suite.log`.
Benchmark final: ataques 2/2, 4/4 y 6/8; 14/14 movimientos, sin fallback ni
fallos de invariantes, tiempos 6,788–9,686 s. Fracción productiva 0,25.
Aceptación manual y carga de cuatro encuentros siguen pendientes.
Presupuesto predeterminado de turno 10 s. Caché persistente del catálogo y
preparación completa de objetivos/rutas separada del trabajo de exploración.
El formato fragmentado permanece desactivado por rendimiento.

## Evidencia histórica

Las revisiones y pendientes siguientes corresponden a sus fechas e imágenes.
El README de E18 contiene las decisiones y pendientes actuales.

# Validación actual — 2026-10-07

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


Puente genérico v3 conservado en world `1ed06b10b4d2`, SDK completo read-only.
AI `56ccebd4faee`, saludable, desplegado16:03:19Z. Reinicios propios world1/3;
world mantiene su inicio externo14:53:48Z. Cliente intacto.

Suite congelada32007 terminal0: **396 pruebas OK**,155,641s unittest y156,328s
global, cero fallos/errores/omisiones.169 módulos del motor únicamente de la
copia completa de esa imagen; manifiestos por archivo antes/después idénticos.
SDK85py SHA `2c97d4fb7ba4099d726a1d9b466523e5e1b89bdfc1a3c17197979b9bb9d10a81`.
Log `.runtime/local/e18-ai-tuple-fallback-frozen-suite.log`.

Banco70638 terminal0,14 turnos completos7075celdas/24556aristas, presupuesto5s:
2/2 ataques individuales (movimiento y daño5 del7962),0/4 con concurrencia2
(4 movimientos),0/8 con concurrencia4 (1 movimiento). Invariantes pasan;
individuales4,997–5,052s, concurrentes3,953–5,185s. No certifica aceptación
concurrente ni GUI. Artefacto `.runtime/local/e18-native-shared-geometry-turns.json`.

Revisión posterior del inventario encolado aún sin desplegar:21 pruebas del
puente OK; suite congelada397 en curso. Las entradas siguientes son históricas.

# Evidencia de entrega — 2026-10-06

Servicio táctico v2 y puente world implementados. World recibe módulos
nuevos y el reemplazo de `pass_test_monster_turn`; no se editaron los handlers
comunes, la base de datos ni el cliente. Referencia Dofus leída, sin ejecución
ni modificaciones. Protocolo 1 conserva su comportamiento. World reiniciado por petición explícita del usuario el 2026-10-06: healthy,
TLS en 15556 y dispatcher en 15558. La ampliación posterior de capacidades
y diversidad aún no está desplegada.

- 17 tests nuevos (`test_tactical.py`): secuencias, daño/remate, curación,
  friendly fire, retirada, XYZ/aristas, ramas sin soporte, ciclos, checkpoints,
  extensibilidad de features, límites y 32 decisiones concurrentes reproducibles.
- 18 tests existentes: `tests.test_ai_service`, `tests.test_combat_ai`,
  `tests.test_combat_ai_client`. Todos pasan con `PYTHONPATH=server`.
- Aceptación HTTP ejecutada sobre servidor real de prueba: secuencia
  mover/lanzar/retirarse, cura, friendly fire, remate, rechazo de revisiones
  ajenas, mismatch del root, JSON inválido y tamaño; protocolo 1 compatible.
- Imagen Docker construida con los cinco módulos de runtime; únicamente el
  servicio `ai` reconstruido/recreado mediante `--no-deps`.
- Aceptación HTTP repetida dentro del contenedor final: todos los casos OK.
  Health confirma protocolos `[1,2]`; Compose marca el servicio healthy.

## Carga sintética

Reproducir: `python3 server/ai-service/benchmarks/benchmark.py`.
40 muestras por escenario, Python local. Mide validación de DTO y búsqueda;
**excluye generación de previews nativos, HTTP, CPU/RAM de world y partidas**.
Se usa deadline 250 ms para medir búsqueda completa bajo carga.

| Escenario | Nodos DTO | Bytes JSON | Workers | p50 ms | p95 ms | p99 ms | Expansiones máx. | Timeouts |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Pequeño | 13 | 7209 | 1 | .224 | .315 | .378 | 12 | 0 |
| Mediano | 85 | 43967 | 1 | 1.178 | 1.439 | 1.583 | 68 | 0 |
| Complejo | 781 | 404961 | 1 | 7.474 | 9.439 | 9.526 | 150 | 0 |
| Concurrente | 781 | 404961 | 4 | 25.932 | 49.760 | 52.009 | 150 | 0 |

Son mediciones del corpus sintético, no un SLA ni validación del presupuesto
inicial 50 ms en producción. Los percentiles de 40 muestras son descriptivos;
para ajuste final faltan corpus de previews reales y partidas/observadores.

## Evidencia del puente world

- 8 pruebas nuevas de `tests.test_combat_tactical_ai`: previews privados,
  presupuestos, stale metadata/context/estado, certificación de acciones,
  barrera ACK/pending, una acción por commit y redecisión entre entregas.
- Wonejo: autoridad propia 7962/nivel 1, daño común 5, usage consumido solo en
  preview; serializer fallido deja HP/recursos/UIDs y contadores intactos.
- HTTP end-to-end: el servicio real recibe el DTO nativo, elige cast, world
  ejecuta/commit y publica; segundo request termina por límite nativo por blanco.
  Se utiliza LOS acreditado por fixture/mock, no una exploración GUI del mapa.
- 31 regresiones de IA/movimiento/ataques NPC/transacciones de hechizos: OK.
- El puente inicial está desplegado en world y ai, ambos saludables. Otros ataques entrarán cuando sus
  árboles/condiciones sean ejecutables; aún no se afirma soporte universal.

## Pendientes para aceptación completa de E18

1. Ejecutar `PRUEBA-WORLD.md` sobre el puente activo; desplegar la ampliación
   posterior avisando antes de reiniciar.
2. Extender los árboles de ataques NPC actualmente pendientes en el motor común;
   el puente no necesita whitelists nuevas para habilidades soportadas.
3. Añadir previsión nativa de amenazas y métricas de estados/zonas: hoy se valora
   posición por alcance/topología y daño localizado por preview, sin bonus Z.
4. Conectar el provider de política al almacén DB cuando se defina el esquema;
   actualmente admite política/versiones inyectadas y foco tras commit.
5. Corpus real de roles, varias instancias, GUI/observadores y coste completo
   bajo carga. Las métricas sintéticas anteriores no acreditan esos escenarios.

Añadir ataques soportados con daño/cura/armadura no exige cambios de IA.
Mecánicas nuevas pueden aportar outcomeFeatures/pesos sin tocar el buscador.
Esto no sustituye la implementación y pruebas del efecto en el motor nativo.

## Ampliación de capacidades

7 pruebas de `tests.test_combat_ai_capabilities`: etiquetas mixtas,
dependencias/ciclos explícitos, afinidad de cura, presupuesto repartido entre
hechizos y movimiento, avance hasta rango de ataque y sanador sin necesidad
de perseguir enemigos. Son fixtures con consecuencias certificadas de prueba,
no validación de ataques NPC que todavía no existen en el catálogo. Dos pruebas
adicionales del servicio validan metadatos y afinidades no excluyentes sin
cambiar la decisión, y rechazan booleanos como IDs, rangos inválidos y duplicados.

Suite conjunta final: 59/59 pruebas del servidor en 65.6 s; 17/17 del servicio.
Aceptación HTTP repetida con servidor efímero local: todos los casos OK.
No se reinició world ni ai para esta ampliación. Durante la validación otra
sesión recreó world con el puente inicial; su imagen no contiene todavía
`combat_ai_capabilities.py`.

## Continuación — 2026-10-07

- Regresión conjunta ampliada: 72/72 antes del último ajuste de contexto/raíces.
  Servicio: 19/19, incluyendo conexiones HTTP limitadas y arenas v2 >8192.
- LOS real de una arista exportada de Amakna1134 verificado sin mock.
- Arena real con 17452 celdas: el DTO conserva el footprint de todos los nodos
  y rutas; no transmite toda la topología para cada acción. El hash sigue
  incluyendo el terreno nativo completo y detecta cambios.
- Perfiles SQL ejecutados en PostgreSQL dentro de un esquema de prueba y
  ROLLBACK; DDL, default y foreign keys válidos. Pruebas de validación y congelado
  por encuentro sin consultas por candidato.
- Fallo observado en la prueba del usuario con jalató: log de fin de turno con
  TypeError. Reproducido con `Store.character` de un personaje real en una
  transacción READ ONLY: el hash anterior falla con datetime; el nuevo admite
  tipos DB y produce hash reproducible. No se imprimieron datos del personaje.
- Previews costosos detectados en mediciones nativas, sin presentarlos como SLA.
  `native-benchmark.json` conserva observaciones; el profiling separa carga LOS
  y expansión. Los deadlines son cooperativos, no interrumpen un cast síncrono.

Para desplegar se prepara una imagen sobre los archivos del contenedor world
que está funcionando, con solo los cuatro módulos de IA, la función integrada
y migración 045. Así la entrega de IA tiene una base conocida mientras otras
sesiones continúan modificando archivos compartidos. No usar una reconstrucción
indiscriminada del checkout como evidencia de este despliegue acotado.

## Despliegue jugable — 2026-10-07

Reinicio avisado antes de ejecutarlo. Solo ai/world recreados, sin dependencias.
World usa `wakfu-local-world:e18-verified`, SHA
`7c5cf3b729cc45fc01a730d2fe47ba1fe43bffb58c7867ecdf2aaf18e278f29c`.
AI usa SHA `623c4d682dad1f7a06642229a218e405188ad184c94f4411e43688604dfc29ae`.
Migración045 aplicada (1 migración); loader instalado leyó perfil normal1 y
congeló la configuración del encuentro contra la DB real. Ambos healthy y
listeners15556/15558/18081 comprobados. Aceptación HTTP ejecutada dentro de ai:OK.

74/74 regresiones conjuntas del servidor. 30/30 gates sobre el árbol exacto de despliegue: bridge, capabilities y policy.
19/19 del servicio. Jalato ref1 nivel8 a seis celdas: decisión MOVE, menor
distancia y snapshot inicial intacto; 5767 descartado por árbol ausente.
Wonejo con LOS nativo real acreditado en una arista exportada.

Después de prewarm_runtime_catalogs + un cast forecast aislado (sin commit),
medición caliente sin profiler: adyacente113.2ms, aproximación112.4ms, ambos
48previews/41transiciones en arena-fixture7celdas; DTO29.6/29.5KiB.
El profiling aparte tuvo157.7ms y19previews: overhead de profiler explícito,
no mezclar con el wall sin instrumentación. No es un SLA ni carga GUI concurrente.

Usuario notificado de que puede volver a entrar y probar jalatós/movimiento y
Wonejos/movimiento+ataque. Aceptación GUI aún pendiente; E18 sigue activo.

## Aceptación del usuario y corpus adicional

El usuario confirmó en juego que Wonejo pega y que jalató se acerca sin pegar.
Logs del combate16 muestran movimiento→7962→fin de turno; los del17 muestran
movimiento y descarte explícito de raíces5767. Ambos combates terminaron y
volvieron al mundo. Esto acredita el flujo inicial jugable, no todos los roles.

La demora reportada coincide con un checkpoint de35567.628ms posterior al
fin de turno de IA. El usuario excluyó explícitamente esa ruta de este trabajo;
solo se investigó, sin cambios en persistencia. Los eventos de IA anteriores
a ese guardado publicaron movimiento/fin con previews160–181ms y servicio
<6ms; no atribuir los35.6s al planner.

Corpus de servicio ampliado:25/25 OK. Los seis casos nuevos acreditan ranking
de forecasts explícitos para AoE con varios afectados/friendly fire, inmunidad
(daño efectivo0), reflejo letal para NPC, amenaza ponderada por perfil, consumo
de AP/WP en secuencia y dosUUID concurrentes. No acreditan exportación de tales
efectos en el motor NPC actual. Sin nuevo reinicio para estas pruebas.

## Respuestas rivales certificadas — 2026-10-07

`rivalForecasts` permite comparar secuencias alternativas de cada rival y
estimar riesgo mediante su mejor resultado adverso. No suma todos sus ataques
alternativos. Conserva modo/dependencias, contempla daño neto de equipo,
armadura, bajas y control; no trata el gasto de PA del rival como daño recibido.
Comprueba cobertura de los mismos rivales vivos en todos los estados, pasos
tipados, rosters y presupuestos globales. Los registros de planes no soportados
también cuentan para el límite; una regresión con8193 registros lo acredita.

Validación: `PYTHONPATH=server:server/ai-service python3 -m unittest discover -s
server/ai-service` →38/38. `PYTHONPATH=server python3 -m unittest
tests.test_ai_service tests.test_combat_ai tests.test_combat_ai_client` →18/18.
La aceptación HTTP añadió retirada ante respuesta rival certificada y rechazo
de amenaza escalar junto con forecasts:6 escenarios y controles de errores OK
en imagen aislada y en el contenedor desplegado.

Se anunció y reinició solo ai-service. Imagen activa:
`sha256:2d9da1ee15b610fc263832e9d8b1f7f57a62621e130474cb5e418dc92dd642f6`.
No hubo cambios en world ni cliente para esta ampliación. World aún no produce
`rivalForecasts`; estos casos acreditan contrato y ranking del servicio, no
amenaza rival nativa activa en juego. Sigue pendiente conectar la proyección
de turnos nativos y resolver contexto de repertorios de rivales controlados.

## Puente completo — preparación y transferencia real

El usuario pidió un único puente definitivo y prohibió recortar datos por
tamaño. Todo el SDK y sus pruebas se preparan dentro de `server/ai-service`;
la integración final en world sigue pendiente de validación. Los dos archivos
experimentales anteriores fuera de esta carpeta fueron retirados sin desplegar.

`native_context.py` transmite el grafo nativo completo por reflexión: campos
dinámicos, dataclasses/slots privados, tipos, bytes, claves enteras, referencias
compartidas y ciclos. Los objetos callable con estado retienen sus campos;
las funciones se identifican sin ejecutar código recibido. `context_store.py`
verifica hashes reales y no declara completo un manifiesto con archivos faltantes
o corruptos. Los bloques limitan el tamaño de cada frame, no del paquete total.

65/65 pruebas de ai-service OK, incluidas21 de grafo, almacenamiento y transporte
HTTP. El sender real recupera un ACK perdido después de persistir un bloque,
sin duplicar bytes ni tratar una respuesta perdida como corrupción del contenido.

Aceptación contra contenedor aislado `wakfu-ai-bridge-check`, puerto18094:

```bash
python3 server/ai-service/scripts/bridge_acceptance.py --url http://127.0.0.1:18094 --catalog-root server/protocol --engine-root server/wakfu_server
```

Resultado:5398 archivos/5398 contenidos únicos,342850028 bytes íntegros.
Manifiesto`33d6fa2d3ef335c90e70ba0a8e70ec0b17ed586c31a4965b9628ecec15afb05a`,
sin entradas faltantes. Segunda transferencia completa produjo el mismo hash.
Esto acredita transferencia e integridad de los árboles reales, no la conexión
del planner v3 ni el commit final. La imagen de prueba no reemplazó world ni ai
en el stack jugable. Falta terminar y acreditar el oracle nativo y el diálogo
de consultas dirigido por ai-service antes de la integración final.
# Actualización: servicio único y catálogo directo

Última reconstrucción del AI actual, mediante `sh server/ai-service/rebuild.sh`:
imagen AI `sha256:d8a66203ab55550f56ef021181e4c0ec7f619e377c71af01e1ef8b89b3a8bdae`.
Catálogo desde world `sha256:3523a0a5c7d5b7b2dd7945095c297fe251522be17cf8c515dfa10c97517d75f9`:
5.397 archivos / 343.024.139 bytes; manifiesto
`3eecaf2a22b4b12fc241a845e1533e9d673254389d4e2851d728e3bf82974fba`.
Health HTTP OK. El script reinició solo AI; world conservó su StartedAt
`2026-10-07T06:29:41.403760511Z` durante esta operación.

Suite completa posterior: `PYTHONPATH=server:server/ai-service .runtime/e18-venv/bin/python -m unittest discover -s server/ai-service/tests`
→ **109 pruebas, OK, 49,609 s**. Incluye negociación/reintentos/HTTP,
Wonejo en mapa completo, commit PC y barreras ACK, más proyección rival y
driver de turnos. La amenaza nueva todavía debe conectarse al ranking v3;
world sigue usando v2 hasta la integración final.

El servicio `wakfu-local-ai-1` fue reconstruido y reiniciado de forma aislada
con `docker compose up -d --no-deps --no-build ai`. Imagen observada:
`sha256:79f72dc30e87977e4ed72dcdf1af9395c48f07289bed118b7ba64062d0b043aa`;
health HTTP y Docker: OK. Catálogo completo dentro del contenedor:
5.395 archivos, 342.732.020 bytes, manifiesto
`d789fa1fbc32b53a52e8f0a69c132ccae95b4d853e0790a7344ea8688a5c6f3c`.

Hay un único `Dockerfile`, con `COPY . /app`. `rebuild.sh` reconstruye AI
desde la imagen exacta del world vivo y reinicia solo AI. Se retiró el
contenedor auxiliar `wakfu-ai-bridge-check`; su prueba histórica se conserva
abajo como evidencia, no como servicio activo.

World conservó imagen
`sha256:9af0658c4e5db5da40debb6ba8c656f248bc10397fb6055a03ae76f215039a28`
y StartedAt `2026-10-07T05:37:51.673000212Z` antes y después de ese reinicio AI.

La negociación `/v3/decide` y el SDK de consultas están implementados dentro
de AI, todavía sin integración final en world. El juego sigue usando el
puente v2 existente. No interpretar la provisión completa del catálogo como
aceptación del sistema táctico completo: faltan certificación de la nueva
integración, amenaza rival activa y pruebas de aceptación del conjunto.

## Verificación completa del SDK — 2026-10-07

- `PYTHONPATH=server:server/ai-service .runtime/e18-venv/bin/python -m unittest discover -s server/ai-service/tests`: 135 pruebas OK, 62,533 s.
- Misma configuración, `-m unittest tests.test_ai_service tests.test_combat_tactical_ai tests.test_combat_ai_policy`: 28 pruebas OK, 62,103 s.
- Incluye cargador privado, autoridades/builds seleccionados, perfiles completos, transporte comprimido sin pérdida y ranking de respuestas rivales. World continúa en v2; integración v3 pendiente. Contador de reinicios de este agente: 0/3.

AI desplegado: `sha256:ba9bf1997d231c11f7ac40a5772c1e114b25d38002681e4c97651da17cab322f`, saludable. Prueba HTTP en el contenedor: transferencia gzip de grafo completo con ciclo y 256 KiB de bytes; recuperación íntegra verificada. World cambió externamente a `63b4642d1a89` a las 07:08:13 UTC; no fue un reinicio de este agente y requiere nuevo cotejo de catálogo. Entrada: 4 pruebas OK, incluida falla de precarga que conserva PA/PM y genera cierre nativo con ACK.

Medición HTTP nativa reproducible: `PYTHONPATH=server:server/ai-service .runtime/e18-venv/bin/python server/ai-service/benchmarks/benchmark_native_http.py`. Usa catálogo completo y `local_arena(1134)` sin reducción, servidor HTTP efímero en localhost, dos pasadas cold/warm y comprobación del grafo fuente intacto. Primera ejecución aún en curso; no hay resultado de latencia certificado.

Resultado de primera medición completa: 7.075 celdas; ambas pasadas seleccionan cast7962 a PC7 y conservan fuente. Cold: preparación11,685s, decisión8,683s. Warm: preparación1,807s, decisión35,722s, solo1 bloque nuevo y7 llamadas decide. **Gate de latencia no aprobado**. Perfilar serialización/guard y previews; no desplegar v3 con estos tiempos. Artefacto local `.runtime/e18-native-http-benchmark.json`.

Ajuste posterior SDK: `world_entry` transmite `native_start_events` conforme a `WAKFU_COMBAT_START_EVENTS`, y el driver rechaza presupuestos NaN/infinitos antes de consultar o mutar. `test_native_turn test_world_entry`: 9 pruebas OK. Perfil cProfile del benchmark HTTP completo aún activo, session87568; no atribuir el coste a una función hasta revisar el perfil terminado.

Perfil terminado `.runtime/e18-native-http.prof`: guard27 calls/26,006s cumulativos, encode41 calls/29,000s; el chequeo íntegro de fuente es un coste dominante. Primera optimización preserva esquema y campos: lookup directo del tipo builtin de contenedores; subclasses mantienen detección/fields. `test_native_context test_native_session test_bridge_context`:22 pruebas OK/8,943s. No hay benchmark posterior todavía: no declarar latencia resuelta.

Huella íntegra de fuente `native_fingerprint.py`: traversal C de contenedores, instance fields explícitos, alias/ciclos, sin ejecutar reducers personalizados ni deserializar los bytes. Grafo completo de transporte no cambió. Regresiones:17 pruebas OK (fingerprint/session/bridge); nueva prueba de cambio de alias: session7 OK. Benchmark posterior sobre las7.075celdas: cold preparación10,341s decisión5,007s; warm preparación1,282s decisión4,998s;52 consultas decide por pasada y selección7962 conservada. Antes warm35,722s/7consultas. Presupuesto de búsqueda del benchmark5.000ms: aún medir perfil normal{} antes de certificar gate. Primer intento posterior falló HTTP400 al cargar catálogo local; segunda ejecución completó ambas pasadas. No esconder ese fallo: diagnóstico HTTP imprime respuesta para futuros casos.

Perfil normal{} antes del ajuste de preparación: decisión1,954s, pero elige end_turn: los250ms se agotaron cargando repertorio/grafo, no explorando candidatos. **Gate funcional falló**. Ajuste query_search: inicializar deadline de exploración después del primer repertorio/grafo completo; preparaciones siguientes siguen contando y límites nodes/query/turn permanecen. Regresión de preparación2s/budget250ms ahora certifica cast y conserva nodes≤4. test_query_search+test_query_search_risk:12OK. Nueva medición real en curso sesión26744; no afirmar todavía aceptación nativa del perfil normal.

Ensayo siguiente detectó HTTP400 checksum mismatch: los archivos fuente pueden cambiar después del inventario. CompleteContextExporter ahora toma snapshots íntegros por SHA, sin filtros, con stat antes/después del copiado y limpieza automática; el transporte usa esos mismos bytes. Regresión modifica original tras inventario y verifica versión anterior íntegra y nuevo manifiesto cambiado. `test_bridge_context test_native_stats`:11OK/9,322s. Nueva medición sesión56477 en curso. NativeStats para autoridades individuales PC/NPC:2OK, summons pendiente encoder validado. Commit rebinda callbacks vivos a autoridad completa y RNG real; nueva regresión nativa preparada (aún pendiente ejecución tras benchmark).

Benchmark completo con snapshots estables terminó OK: normal{} cast7962,7.075celdas, decisión1,988565s preparación1,314030s,fuenteintacta. Cold12,327707s+4,899570s y warm1,294619s+4,872117s con budget5000ms. `.runtime/e18-native-http-stable-result.json`. Última suite145OK/44,927s antes de agregar encoder summon; entrada/stats8OK posteriores. Nuevo focal NativeOracle96925 en curso, con huella de commit rápida y callbacks serializer registrados completos.

Cierre de esta verificación: NativeOracle9OK/44,108s y suiteactual147OK/57,635s. Incluye world_entry NativeStats por actor, registro summon actual en serializer de boundary y huella commit completa rápida. Diferencial JAR consumidor12873/eHD UID901 con cuerpo real snapshot_characteristics+monster_actor_stats y patchúnico q terminal:resources853/5/5/3→17/4/2/2,ref1153level20preservados;UID902sinregistroignorado. Comandos/hashes/shimgráficoenINFORME-SERIALIZACION-SUMMON-12873.md. No cliente/world editados ni reiniciados en estas verificaciones;contador0/3.


## Catálogo reutilizado y grafo completo por nodos — 2026-10-07

Suite completa actual: `PYTHONPATH=server:server/ai-service .runtime/e18-venv/bin/python -m unittest discover -s server/ai-service/tests`: **153 pruebas OK / 78,924 s**. Incluye roundtrip nativo Wonejo, rutas completas, contexto fresco por acción y equivalencia byte a byte del encoder completo.

Benchmark `.runtime/e18-native-http-stream-result.json`, arena completa de 7.075 celdas y política normal: sin reutilizar catálogo preparación1,40586s/decisión2,28502s; reutilizándolo preparación0,34977s/decisión2,27157s. Todas las pasadas seleccionan cast7962 y conservan la fuente. Los registros anteriores mostraron pausas de9–18s durante registro; esta ejecución no las reprodujo después de serializar cada nodo completo y liberar el cierre recursivo. No se modificó GC global ni se recortaron campos, catálogo o grafo. Falta acreditar el límite del turno completo con varios commits y ACK; estas cifras son de negociación individual.

Límite persistente del usuario: máximo tres reinicios de world; después del tercero no habrá más cambios. Avisar antes de cada reinicio. Contador de este agente: **0/3**. Ningún reinicio realizado en esta validación.

## Validación del puente final — 2026-10-07

- Suite AI y regresiones raíz: 205 pruebas, OK, 59,919s.
- Turno compartido HTTP completo: arena7075 celdas/24556 aristas; cast7962 certificado/comprometido a4,110s, HP60→55. Cierre nativo por fallback a5,269s; publicación del lote a5,335s. ACK real pendiente, sin respuesta simulada. Preparación1,742s. Evidencia `.runtime/native-shared-turn-http-budget5.json`.
- Imagen viva `2e64d4e0730b` todavía sin integración COMBAT_SESSIONS: 22 pruebas entry/hook/loader/stats/source aprobadas en contenedor efímero sobre esa imagen. La ruta compartida se valida contra el motor nuevo del checkout; no está disponible en esta imagen antigua.
- Se rechazó publicación compartida sin paquetes antes de adoptar candidato; regresión comprueba fuente, secuencia y outboxes intactos. Preparador AST conserva bytes fuera de la única función acordada; 10 pruebas enfocadas aprobadas.
- Reinicios world propios desde la instrucción de máximo tres: 0/3. Puente final aún no desplegado; v3 no acreditado como jugable.

### Despliegue del puente final

World `ff2659e929a2` usa como base exacta `2e64d4e0730b`; única diferencia de código: función `pass_test_monster_turn`. SDK montado read-only `/app/ai-service`. AI actualizado a `6f7b4d912f5f`. Reinicio propio1/3, avisado previamente; después del tercero no cambiar nada más. Antes del despliegue, 16 pruebas nativeOracle/turn contra imagen viva pasaron; una falló por import de auxiliar de tests y, corregida su ruta, pasó aislada (153,663s, incluye prewarm). El cierre/GC del proceso de prueba nativo se mide aparte; no se confunde con latencia del turno. Falta aceptación conectada al juego.

## Coordinación confirmada y capacidades observadas — 2026-10-07

Suite conjunta AI+root220OK /68,395s. Ensayo compartido completo7075celdas/24556aristas con foco anteriormente confirmado: el servicio recibió teamContext focusId7 y UUID/revision/team correspondientes;17sourceGuards OK. Cast7962 comprometido a4,321s, HP55→50. Fallback endTurn5,254s/publicación5,282s; ACK cliente pendiente. Historia confirma después del broadcast y armAck o tras envíos locales completos, no en previews/candidatos descartados. Pruebas posteriores de historia32, fallo de envío, mutación de book invalida guard, contexto focus transmitido y capacidades observadas:48 enfocadas OK. Reservas/corredores todavía no son producidas automáticamente; roles y métricas explicativas espalda/altura siguen pendientes. No worldrestart adicional:1/3.

Última suite conjunta ejecutada por Luna:227tests OK /56,903s, cero failures/errors/skips. AI desplegado `03a943a538f9`, saludable; loader privado del servicio importa query_search/capability_evidence correctamente. World conserva imagenff2659e929a2 y StartedAt2026-10-07T08:53:28.678332466Z: no reinicio adicional. Manifiesto completo revalidado en AI `596fae32baf740ac48deb083afc3f9598927d654d4eeab510bc8901e83c4b0ea`,11041entradas, missing=[]; corresponde a ese momento del SDK/documentación. Ajuste posterior SDK del registro neto de bajas y curación:32pruebas enfocadas OK; no cambia selector HTTP ni puente world. Atribución explicita published_transition_net_outcome, no atribución de caster inventada; la baja queda en historia y nunca como foco vivo.

## Topología dirigida XYZ y preparación parcial — 2026-10-07

44tests enfocados OK0,040s; transporte/bootstrap/topología/session29OK10,271s y nuevo HTTP300assets+1changed1OK0,859s. NativeSession emite mediciones topológicas desde el mismo runtime completo registrado. Ruta/score no inventan aristas reversas ni ventaja por Z; las previews siguen certificando footprint/LOS/costos. Se valida edges⊆walkable. Inactivo conserva utilidad de posición raíz, no gana bonus por muerte. Distancia desconocida versus inalcanzable se distinguen; fallback de snapshots sin nuevo campo es XY y explícito.

Ensayo nativo HTTP shared completo7075celdas/24556aristas: después de una pasada sin ataque (prep2,779s, timeout), el ensayo estable volvió a cast7962 a4,209s (HP55→50), preparación1,690s, decisión2,519s, cierre nativo5,272s y publicación5,316s. Sourceguard17OK, foco7 recibido; ACK turno1 pendiente, sin simular cliente. Cálculo topología2actores23–26ms. Medida aparte sobre el mismo terreno real:2actores20,97ms,8actores35,40ms,32actores98,32ms,64actores150,63ms; esto solo acredita costo de medición, no latencia concurrente del turno. Artefacto `.runtime/native-shared-turn-http-budget5.json`. Fast partial manifest usa sealed.missing y rehash final completo, sin scanstatus de todos los archivos presentes. No reinicio world adicional:1/3.


### Estado verificado y límite de reinicios

Suite conjunta más reciente: 240 pruebas OK /58,069s, sin errores, fallos ni omisiones. Incluye geometría XYZ dirigida, registro confirmado, integridad de fuente y transporte parcial de300 archivos con validación completa final. AI actual `6b7cfea7f077` y world `6319c87dedd6`, ambos saludables. World fue actualizado por otra sesión a las09:27:25 UTC; conserva el puente genérico y el montaje SDK. Contador de reinicios de este agente:1/3; avisar antes de cada reinicio y no hacer más cambios después del tercero. Los hashes de catálogo anteriores son evidencia histórica, no la validación del manifiesto del despliegue nuevo.


### Diversidad y prioridad por capacidades

24 pruebas focales OK /0,029s. El beam conserva el mejor global y mejores categorías intent/target antes de duplicados; las etiquetas observadas solo ordenan blancos y conservan todas las celdas. Regresión integrada sobre oráculo simulado: beam2 conserva heal8 pese a dos ataques10, su continuación certificada produce heal8+damage40 y gana por utilidad. Esto prueba búsqueda, no nuevas fórmulas ni efectos nativos. Catálogo world actual+SDK revalidado: SHA5592a6cee359a6ff3a86cb854206e9ba22df561411783396db9aee01171f15d6,11046entradas,689574543bytes,complete=true,missing=[]. No reinicio world;1/3. Suite conjunta y despliegue del cambio de búsqueda pendientes.

Suite posterior ejecutada una vez por Luna:243tests OK /72,979s (elapsed73,221s), sin errores/fallos/skips. La nueva regresión se añadió después de recoger esa suite y pasó aislada1/1 OK /0,005s; no afirmar una única suite de244. Primer intento de import aislado usó un prefijo tests inválido, corregido antes de ejecución. Despliegue AI posterior en curso, world intacto.

Despliegue completado: AI2f56afae5fc6 saludable, /health protocols[1,2,3]. Módulo desplegado conserva attack10+support8 con beam2 frente a duplicate9. World6319c87dedd6 mantiene StartedAt2026-10-07T09:27:25.695715121Z: ningún reinicio world en este cambio. Contador propio1/3. README y prueba general actualizados; aceptación en juego y resto del alcance E18 pendientes.


## Corredores de tiro por autoridad nativa — 2026-10-07

SDK prepara propuesta solo para cast NPC elegido con LOS obligatoria y enemigo vivo. Usa los mismos cast_rays/_resolve y footprint que authoritative_visible; no Bresenham ni altura elegida arbitrariamente. Confirma únicamente después de publicación. Consumidor revalida dueño/objetivo/turno/revisión/UUID/TTL y bloqueadores actuales; comparte solo con otros aliados. Peso de coordinación se aplica como delta blando de ocupación de huella, nunca como rechazo legal. Reservations de movimiento/intenciones futuras todavía pendientes.

Suite conjunta de Luna254OK61,285s (elapsed61,498s). Revisión encontró coordinate source=None/target=int que podía provocar TypeError: validación XYZ previa y regresión añadidas. Prueba adicional usa rayos reales de Amakna y concuerda con authoritative_visible antes/después de blocker. Focal final49OK0,902s, incluye ambas nuevas pruebas. No afirmar que256 corrieron en una única suite.

Benchmark NUEVO ejecutado directamente por root: session20859 terminalexit0, artefacto `.runtime/native-shared-turn-http-budget5.json` actualizado mtime1791366968.401487. 7075celdas/24556aristas, prewarm20,509s/provisión9,370s fuera del reloj; prep2,114s/decisión2,711s, cast7962 a4,829s HP55→50, cierre5,002s/publicación5,024s,15sourceGuards intactos,9FIFOpackets yACK1 armado sin simularcliente. coordinationDraft=null: no acredita reserva publicada en este cast. La primera comunicación del agente de pruebas repetía tiempos del artefacto viejo; retiró esa afirmación y estas métricas corresponden a la ejecución nueva verificada directamente. Despliegue de esta capa pendiente, sin reinicio world adicional1/3.

Despliegue de corredores completado: rebuildsession11029 terminalexit0. AIeb97ab21be28 healthy y /health protocols[1,2,3], módulos corridor_reservations/scoring presentes. World6319c87dedd6 healthy con StartedAt2026-10-07T09:27:25.695715121Z intacto; contador propio1/3. Benchmark Registry corresponde al motor del checkout, no acredita que el world vivo haya incorporado COMBAT_SESSIONS ni reservas en GUI.

Catálogo postdespliegue recibido desde world actual+SDK por puente y rehash íntegro en AI: SHA62148b34e04411d7c9a619c6b768dc0712ea9a2ec0cd5934c46d631799c063b6,11050entradas,689630916bytes,complete=true,missing=[]. Estos valores describen el snapshot verificado antes de registrar esta evidencia, no modificaciones posteriores del SDK/documentación.


## Recibos completos de preview y deduplicación — 2026-10-07

NativeSession.preview conserva packets/transaction/action/sourceState/publication en el mismo grafo que runtime/authorities/flags. NativeOracle rutas state ybytes retienen alias de fight y todos los campos futuros de tx. Oráculo legacy conserva también su graphoriginal completo bajo completeState. Etiqueta uncommitted_native_preview explícita; source guard y certificación fresca siguen requeridas.

RuntimeIdentity fullfingerprint(runtime+authorities+flags) separado del contentaddress key/transitionContext: visited/beam/shortlist de búsqueda y forecast deduplican runtime; consultas recuperan el key del recibo. Pruebas cubren binarios/campos futuros/alias/no mutación, dos recibos distintos de un mismo runtime, un futuro campo nativo que cambia identidad y la conservación de apoyo al deduplicar. 50focales OK0,058s; suite final260OK65,963s (elapsed66,188s), sin failures/errors/skips. Suite anterior25865,058s precede a la corrección de identidad. Revisión read-only no encuentra bypass de commit.

Limitación de orientación comprobada en fuentes: DamageExecutionContext y FRONT/BACK/SIDE usados durante aritmética no se guardan en SpellTransaction; outcomes son booleanos. No dar crédito diagnóstico de localización por efecto usando solo el recibo, ni añadir bonus por dirección. Medición nativa y despliegue de esta capa pendientes; world1/3 sin nuevo reinicio.

Benchmark nuevo directo root, session15281 terminalexit0: arena7075celdas/24556aristas, preparación1,726s/segunda0,375s, commitcast7962 a4,146s HP55→50, cierre5,287s/publicación5,307s,17guardsintactos,9paquetesFIFO,ACK1 armado sin cliente simulado. Recibos completos y runtimeIdentity activos durante esta pasada. Cancel request0,269s de cleanup; presupuesto cooperativo, sin garantía dura de5s. Prewarm21,278s/provisión8,598s fuera del reloj. Artefacto `.runtime/native-shared-turn-http-budget5.json` actualizado; una pasada no prueba percentiles ni concurrencia.

Ampliación posterior: el SDK observa el callback de daño nativo exactamente
una vez y congela contexto, actores, plan, efecto e invocación completos en
ese instante. El preview real del Wonejo conserva estado, paquetes, resultados
y fuente; ContextVar se limpia incluso ante error y aísla hilos/consultas.
Suite conjunta269 OK57,892s (58,442s totales), session15194 terminalexit0.

Benchmark directo root session28384 terminalexit0: ataque4,274s HP55→50,
cierre5,255s/publicación5,276s;17 guards intactos,9 paquetes FIFO,ACK1 armado
sin cliente simulado. Evidencia FRONT real en orientationEvidence; arena7075
celdas/24556 aristas. Prewarm48,718s/provisión8,834s fuera del reloj.
Inventario de esta prueba local:12226 entradas/701531422 bytes; no confundirlo
con el manifiesto del contenedor vivo. Una pasada no acredita percentiles.

Revisión encontró que un error de encode podía rechazar un callback válido.
Corregido después del benchmark: evidencia explicitamente unavailable y
complete=False, devuelve el mismo contexto.30 focales OK0,036s; repetición
de suite completa posterior aprobada:270 pruebas OK49,748s (50,203s totales),
session84639 terminalexit0, cero fallos/errores/omisiones. Despliegue exclusivo
de AI terminal16588exit0: imagen f6be56cae4be, health protocolos1/2/3 y loader
privado aprobados. Catálogo c14112106feda5bc:11048 entradas/689708692 bytes,
rehash completo complete=True missing=[]. World e839fd35a2c1 conserva inicio
2026-10-07T10:38:41.858065287Z y puente/volumen read-only; sin reinicio propio.

Corpus posterior de posición/apoyo:55 focales OK0,135s. Nueva prueba real
NativeOracle rodea por cuatro aristas ortogonales y elige BACK por incremento
de daño efectivo; mantiene fuente completa y guard intactos. Test aislado
terminal72539exit0,1 prueba16,725s. Solo LOS se fija a True en la fixture mínima:
acredita búsqueda, movimiento/transacción y aritmética, no LOS de ese mapa.

El caso de apoyo usa un oráculo de contrato: cast fuera de raíz y legal solo
tras subir por una aristaXYZ, beam2; recupera8HP sin bonus por movimiento.
Sin efecto útil no gana la ruta de apoyo. Otros casos acreditan igualdad del
conjunto de rutas/casts, falta de duplicados y descarte de hechos extranjeros,
otros blancos o distancia desconocida. No demuestra un NPC curador jugable.

Suite conjunta terminal23286exit0:276 pruebas OK59,875s (60,686s totales),
cero fallos/errores/omisiones. Revisión read-only: no filtro/bonus detectado;
límite pendiente son movimientos laterales que abren LOS sin reducir distancia
y protección de aliados con HP completo.

Medición HTTP posterior terminal99594exit0:cast4,738s HP55→50,
end-turn5,008s/publicación5,029s,15 guards intactos,9 paquetesFIFO,
ACK1 armado sin cliente simulado. Preparación2,241s; prewarm18,166s y
provisión9,215s fuera del reloj. Arena7075celdas/24556aristas; se mantiene
evidenciaFRONT real. Una pasada no acredita percentiles ni concurrencia.

Despliegue AI exclusivo terminal2774exit0:58413db8dc02, inicio
2026-10-07T10:59:42.254790687Z, health protocolos1/2/3 y loader aprobados.
Catálogo65c45a2cc2778bff:11048 entradas/689711986 bytes; rehash íntegro
complete=True missing=[]. World e839fd35a2c1 mantiene inicio
2026-10-07T10:38:41.858065287Z. Reinicios propios1/3.

Banco concurrente dentro del world real, HTTP contra AI58413db8dc02:
primer intento terminal16249exit1 por bug del banco al leer identidad final
fuera de decision; ninguna conclusión funcional de esa pasada. Corregido y
cubierto por3 tests (query/final legítimos, fuentes extranjeras, UUID ajeno).
Segundo intento terminal21228exit0,14 turnos en cohortes1/2/4 con2 repeats:
invariantes fuente intacta/UUID/futureMarker/publicación única/ACK sin recibos
correctos; ataques1/2,0/4,0/8. En cohortes4,0 búsquedas iniciadas: cierre correcto
no significa AI funcional bajo carga. Tiempos3,003–5,320s. Prewarm29,796s y
catálogo5,140s fuera del reloj; RSS pico SDK4.360.585.216 bytes acumulado.
Artifacto baseline preservado en .runtime/local/e18-native-concurrent-turns-baseline.json.
Muestra pequeña, percentiles nearest-rank empíricos, sin acreditar SLA.

Preparación optimizada: casts pueden empezar antes de decodificar las24556
aristas de movimiento, que siguen completas cuando se exploran; cache del
inventario usa stat(device,inode)+firma completa, mantiene hardlinks/alias,
reemplazos y archivos futuros. No se evita enumeración ni rehash del receptor.
50 focales OK0,053s,28 HTTP/catalogue focales OK9,911s; suite conjunta final
terminal43243exit0:281 pruebas OK51,110s (51,581s totales), cero fallos,
errores u omisiones. Despliegue AI exclusivo y nueva medición pendientes.

Despliegue completado: rebuildsession7700 terminalexit0; AI67fe32398bf0 healthy, /health protocolos[1,2,3], query_identity presente. World6319c87dedd6 healthy mantiene StartedAt2026-10-07T09:27:25.695715121Z; no reinicio adicional, contadorpropio1/3. Documentado contrato v3 de recibos/identidad en README del servicio. Falta orientación por contexto aritmético y aceptación completa en juego.

Catálogo del world vivo+SDK postdespliegue: SHA3f000e85c0c17608c8409551ef76fd4bfabcacc07a8792aef0fba65180d3cb7a,11052entradas,689656214bytes; ContextStore.manifest rehash completo complete=true/missing=[]. Loader privado queryservice también importó correctamente la ampliación. Snapshot verificado antes de registrar esta evidencia; cambios posteriores de documentación producen otros hashes.


## Presupuesto de búsqueda — 2026-10-07

El ensayo HTTP distante con AI ac8c8ca87419 completó dos turnos sin
movimiento ni ataque: 3,130/2,952 s, expanded1, cast fuera de alcance,
end_turn. No acredita aceptación de aproximación. La corrección separa
espera nativa de trabajo local, transmite presupuesto restante desde SDK y
reserva500ms para certificar/commit, sin ampliar el plazo del dueño.
`PYTHONPATH=server/ai-service:server python3 -m unittest discover -s
server/ai-service -p test_query_search.py`: 12 pruebas OK /0,015s.
Despliegue y ensayo distante nuevo pendientes. World permanece sin reinicio.


## Scheduler incremental — 2026-10-07

`probeQuantum=2` conserva cursores completos de acciones y repertorios;
prioriza continuaciones certificadas tras cada quantum. Módulo de búsqueda
17/17 OK /0,026s. Suite conjunta293/293 OK /90,323s (90,938s total),
sesión92148 terminal0; incluye emisión SDK de nativeBudgetMs acotado y
ausente sin deadline. Rebuild solo AI terminal0, sesión59188, imagen
b9acc96d742d29253958e0d34166384acc9855a5efb919cd2daf99fa3d06149e.
Banco distante real activo sesión84219, artefacto futuro
`/data/e18-native-distant-quantum-turns.json`.
Revisión: beam por quantum no limita frontera global; prioridad DFS puede
postergar candidatos raíz. No declarar solución completa por estas pruebas.
Follower de plan pendiente: identidad forecast y commit difieren incluso en
move (callbacks, serializer, metadata de entrega); cast además usa RNG real.
No omitir campos de identidad ni adoptar previsión para simular commit.


## Reparto global, sesiones independientes y fixture nativo válido

Suite conjunta307 pruebas OK /123,175s (elapsed123,742s), sesión30761
terminal0. Incluye beam global y fairness19 regresiones de búsqueda;
locks por sesión18 fake/HTTP, creator/retry y cleanup bajo exclusión
por entrada; fixture con PV inicial antes de snapshot y preflight nativo
de todos los actores,4/4 OK /3,159s.

Ensayo anterior b9acc96d742d, sesión84219 terminal0: prewarm650,793s
fuera del plazo de turno, un caso válido publicó movimiento+ataque5,028s;
el segundo fue rechazado por 'Characteristic snapshot disagrees with live
actor' tras mutar HP luego de snapshot. Artefacto preservado
`.runtime/local/e18-native-distant-quantum-turns.json`. No clasificar ese
rechazo de fixture como incapacidad táctica ni aprobar rendimiento general
con bancos históricos que carecían de preflight de características.

Despliegue soloAI terminal0, sesión36434, imagen
4aa49a03651c07f23cca7c52f351f5d94e63eaecefdfdae2b67a02d734cb82fa,
health healthy, start12:15:39Z. Worlde839fd35a2c1 sin reinicio,
start10:38:41Z healthy. Bootstrapb0289ed30da2/689.738.394bytes.
Banco HTTP real corregido, NPC distante(-5,-7,-1), cohortes1/2/4×2,
terminado sesión54895, exit0; artefacto local
`.runtime/local/e18-native-fair-concurrent-valid-turns.json`.
Resultado: 0/14 ataques; movimientos 2/2, 2/4 y 0/8 por cohorte.
Todas las comprobaciones de características, fuente, UUID, publicación y
armado de ACK pasaron. Esto todavía no demuestra un sistema jugable.

Cambios posteriores en revisión, todavía sin desplegar: decodificación de
geometría con igualdad de datos y hashes en 7.075 celdas y 24.556 aristas;
preparación completa del contexto excluida únicamente del presupuesto local
de exploración, conservando el plazo real del propietario; copia privada
completa del catálogo para evitar revalidar sus bytes en cada turno.
`PYTHONPATH=server:server/ai-service .runtime/e18-venv/bin/python -m unittest test_query_search`:
23 pruebas OK, 0,030 s. La medición local de geometría pasó de 62 a 6 ms
para celdas y de 114 a 73 ms para aristas; no es una medición de turnos reales.

Despliegue posterior `c321f613a16d` saludable, world intacto. Suite321 OK.
Banco completo sesión84576 terminal0, artefacto
`.runtime/local/e18-native-sealed-context-turns.json`: 0/14 ataques, un
movimiento en cohorte2; todos los invariantes pasaron. Preparación de catálogo
individual 0,29–0,31 s. Perfil local del primer movimiento mostró que la
decodificación de aristas domina su preparación; el límite local descartaba
esa acción antes del preview. Se separó únicamente `_sequence` del presupuesto
de exploración, conservando búsqueda de rutas, ordenación y evaluación
contabilizadas, y el plazo real intacto. Dos regresiones nuevas comprueban
move+cast con geometría lenta y rechazo por plazo real vencido.

Suite conjunta posterior (handle70571, terminada): **323 tests OK**,
132,542 s de unittest /133,248 s totales, sin fallos, errores ni omisiones.
Selección: discovery de `server/ai-service` más `tests.test_ai_service`,
`tests.test_combat_tactical_ai`, `tests.test_combat_ai_policy` mediante venv.

Despliegue d2cadcaeeeded6fd3555f3d7a4de6002d638daab33cf329af371649fa6dcab56,
rebuild82872 terminal0; AI saludable start12:56:46Z; world mismo image/start.
Banco84693 terminal0, `.runtime/local/e18-native-lazy-preparation-turns.json`:
0/14 ataques, movimientos2/2,1/4,0/8, sin fallos de invariantes.
Ambos individuales seleccionaron move+cast nativo; expanded8/6,
preparación1596/1904ms y espera2046/2049ms. El primer cast previsto estuvo
disponible a2,55/2,89s, pero se siguieron explorando alternativas hasta
dejar tiempo solo para el movimiento real. Pendiente reservar tiempo para
commit y replanificación completa después de cada acción.

Límite por decisión `policy.searchTimeFraction` defecto0,5: incluye tiempo
de consultas, preparación y forecast, se fija con el primer hint y no se
renueva. Contexto completo y certificación nativa permanecen obligatorios.
27 pruebas dirigidas OK; suite conjunta handle81634 terminal: **325 tests
OK**, 74,134 s /74,693 s totales, cero fallos, errores u omisiones.
Pendiente banco real: una fracción fija puede cortar antes de hallar un
plan útil si la preparación es lenta; no constituye garantía de jugabilidad.

Despliegue3968bd5de6865e02191e644d85543f1ea8affefc7ee3f5e2b7938914e0f82bd8,
rebuild54439 terminal0, start13:02:26Z saludable; world sin cambios de image/start.
Banco66297 terminal0, `.runtime/local/e18-native-decision-wall-turns.json`:
2/2 ataques individuales reales (move+cast7962), 4,853/5,035s, 0/4 y0/8
concurrentes, todos los invariantes pasaron. Prewarm174,207s y primer
catálogo6,926s fuera de turnos. Observación durante preparación: otros dos
contenedores nativos rondaban100%CPU y3,1/3,6GB; no afirmar SLA aislado.
Primer individual planmove+cast tras3previews, luego freshsearchcast; segundo
primero seleccionó solo movimiento y luego freshsearch certificócast.
Queda pendiente aceptación GUI y rendimiento concurrente.

Root reutilizado por argumento explícito `root_graph`, preservando payload y
leyendo/validando íntegros los sucesores. Nuevo recorrido scandir conserva
todos los archivos y guards. 42 pruebas dirigidas OK /11,654s. Comparación
soloenumeración `/app` del world vivo: 5673 rutas idénticas, 74,195ms anterior
y27,572ms nuevo; no acredita latencia completa de turnos.
Suite30624 terminal: **328 tests OK**, 164,937s /165,679s totales,
sin fallos/errores/omisiones. Build61625 terminal0, imagen
76436fb692fee23ae05d7a291ee874fe1094b8c29d469881cc8d5f779734ba52,
start13:12:53Z saludable, world mismo image/start. Banco30773 activo,
prewarm iniciado; salida `/data/e18-native-root-reuse-scandir-turns.json`.


Actualización posterior: AI8cac53cf86bc desplegado y saludable, suite332
pruebas OK /161,220s. ContextStore conserva snapshots completos por hash en
archivos privados compartidos entre versiones; las verificaciones canónicas
siguen recalculando SHA y los archivos privados conservan guards de identidad.
NativeGraph valida referencias sin sets temporales y rechaza los mismos
formatos/tipos inválidos. Worlde839fd35a2c1, inicio10:38:41Z, sin reinicio
propio adicional (1/3).

Banco49663 terminal0, artefacto recuperado en
`.runtime/local/e18-native-frozen-delta-turns.json`: 2/2 ataques individuales
con movimiento+cast7962, 0/4 con concurrencia2 y0/8 con4. Ningún invariante
falló. Prewarm147,475s y catálogo inicial18,388s fuera de turnos. Con4,
67,931–93,694s por turno sin solicitudes de búsqueda a AI. Observación
independiente: VmRSS1785056kB y VmSwap2411760kB en el banco; Docker top
también demoró y había otros contenedores nativos activos. Hubo cambios
de catálogo durante esa incidencia: no es comparación aislada de rendimiento.

Cambios actuales sin desplegar: alternancia exhaustiva cast/move con rotación
de todos los hechizos; inventario agrupado solamente durante admisión de2ms
anterior al recorrido completo, escaneos posteriores en lotes distintos y
deadlines individuales. Batería dirigida conjunta50 pruebas OK /18,830s.
Batería completa sesión75552 en ejecución; errores de oráculo nativo
notificados durante la corrida, pendientes de traceback final. No desplegar
con base en la batería anterior.

Suite75552 terminal1: varios errores NativeOracle/NativeTacticalPreview
con UnboundLocalError en combat_retained_runtime.container, rama metadata
de spell que usó identity sin asignarla. No hay total verificable porque
la salida quedó truncada. Lectura posterior del checkout ya contiene la
asignación antes del return; corrección ajena a este agente, sin cambios
a world por E18. Se repite suite con captura íntegra y hash antes/después
de ese archivo. La imagen viva conserva la implementación anterior sin
esa regresión. No mezclar checkout en edición con imagen desplegada.

Repetición9590:341 pruebas OK /166,317s, global166,897s, cero fallos,
errores u omisiones; log completo `.runtime/local/e18-ai-current-suite.log`.
El wrapper shell terminó1 por variable readonly de zsh después del runner;
no fue fallo de unittest. El hash del motor nativo cambió durante la corrida,
por lo que no acredita un checkout inmutable. Build15540 terminal0 usa
exclusivamente la imagen viva del world, sin reconstruir ese checkout.
AIeba5c0c628af0e89ff825c9c037d9bf6e3f7d585b7ad34633e035de5ceb41e59
healthy, inicio13:59:17Z. World conserva image/start; contador1/3.

Banco88495 terminal0, artefacto recuperado
`.runtime/local/e18-native-batched-alternating-turns.json`:
ataques2/2,0/4,0/8 para concurrencias1/2/4; movimientos2/2,4/4,2/8.
Todos los invariantes pasan. Individuales4,986–5,151s; con2,4,875–5,320s;
con4,4,232–5,160s. Prewarm27,605s y catálogo5,876s fuera de turnos.
No acredita SLA ni ataque concurrente. Con2 primera decisión solo move;
segunda búsqueda empieza3,891–4,555s. Con4 hay8 búsquedas pero solo2
movimientos. Inventario inicial0,32–0,36s; llamadas posteriores recorren
otro lote completo y esperan1,54–1,99s. El SDK permaneció sin editar
durante el ensayo. La carga externa difiere del ensayo anterior: no atribuir
la reducción de67–93s enteramente a la agrupación de inventarios.

Ampliación siguiente: fuente deAI estable durante suite49842 terminal0,
363 pruebas OK /98,810s,99,377s globales, sin fallos/errores/omisiones.
Hash antes/después de todos AI*.py:
07a4e8c5d32cbf73a9ecda30b3c8fb2dcd24e9290503f6989f262fa74ff78fba.
Hash motor combat_retained_runtime también estable84a23c5a8007dbb9…
Log completo `.runtime/local/e18-ai-extended-suite.log`. Incluye provider
privado completo de features v3, mediciones ausentes desconocidas, cache de
adjacencia nativa y commit inmediato con guard previo y revalidación nativa.

Después se reutilizó JSONEncoder por grafo en lugar de construirlo por nodo.
49 pruebas dirigidas OK /0,407s. Comparación local de geometría7075celdas
/24556aristas:5,462,725bytes exactamente iguales, SHA
25a9b58b8c5d524edb51ab573f4b8180b69d4e43fe1508658ac86689033e1517,
medianas5 muestras0,36684s anterior/0,30681s reutilizado. Solo serialización
de ese grafo, no turno completo; no acreditar concurrencia por esa cifra.
Pendiente build exclusivo deAI y banco nativo de todos los cambios.

World cambió a1ed06b10b4d2, inicio14:18:11Z, por otra sesión; puente y
volumenAI intactos. Banco74685 terminó137 durante prewarm, sin artefacto
válido. EventosOOM consultados vacíos: no atribuir a memoria sin evidencia.
Este agente no reinició world (1/3). Build38744 terminal0 actualiza catálogo
completo desde imagen viva; AI2b3fcff9b409 healthy, inicio14:21:58Z.
Copia completa del motor en `.runtime/e18-world-native-1ed06b10b4d2`.

Banco74384 host contra mismoAI HTTP, motor copiado, terminal0 y artefacto
`.runtime/local/e18-native-extended-handoff-host-turns.json`:0/14 ataques;
movimientos1/2,4/4,2/8. Todos los invariantes pasan. Diferente ubicación de
ejecución/motor/carga respecto a88495: no comparación aislada de rendimiento.
Primer individual seleccionó cast trasmove, pero venció antes del commit;
segundo cerró sin expandir. Fallbacks registrados son TimeoutError.
Sigue pendiente ataque concurrente y jugabilidad distante en versión actual.

Se añadió evidencia del límite que detiene la búsqueda: stopReasons y
searchWorkMsAtLastBudgetCheck, usando el mismo clock/check existente, sin
aumentar presupuestos.47 pruebas query/risk/features OK /0,473s. Necesita
despliegue y ensayo para distinguir agotamiento local, slice y reserva.

Telemetría desplegada en AIbd7d711f99f043832a2163a95640e691cd5a6e7306dfadee6e4ffb316fc83f36,
build30067 terminal0, inicio14:29:33Z healthy. World1ed06b10b4d2 conserva
inicio14:18:11Z; contador propio1/3.
Banco12850 terminal0, SDK/motor copiados y ejecutados desde misma raíz;
`.runtime/local/e18-native-frozen-sdk-budget-evidence-turns.json`:
ataques2/2,0/4,0/8; movimientos2/2,2/4,0/8; todos invariantes pasan.
Individuales4,962–5,092s; concurrentes3,481–5,258s. Todos los cortes
observados fueron decision_wall_budget (a veces también reserva nativa),
con0–83ms de250ms de trabajo local. Preparación/espera agota el tiempo
total. Próximo cambio en implementación: fragmentos de terreno nativo
congelado para serializar los mismos bytes/referencias sin recalcularlos
cada vez. Futuros campos/tipos deben usar camino completo si no son
estáticamente cacheables. No aumentar presupuestos para ocultar el coste.

Ensayo3476 (`--cold-catalog`, motor prewarm como en arranque world)
terminado exit0: **2/2 turnos con movimiento y ataque7962**, daño5 en ambos,
sin fallback ni fallos de invariantes. Tiempos9,209–9,693s; preparación
de catálogo primera4,630s, segunda inferior. Evidencia:
`.runtime/local/e18-native-cold-catalog-owner-world-live-turns.json`.
Se pidió repetir pelea nueva y comprobar primer Wonejo; aceptación manual
todavía pendiente. No reinició world.
