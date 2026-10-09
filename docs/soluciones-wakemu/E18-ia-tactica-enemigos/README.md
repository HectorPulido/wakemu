# E18 — Motor de IA táctica de enemigos

## Investigación activa — 2026-10-08

**Aceptación básica confirmada por Hector (2026-10-08):** el movimiento
parece funcionar; reportará si vuelve a fallar. Combates 71/72 registrados a
19:01/19:03 UTC entregan MOVE a 2,898–3,540 s y end-turn a 4,212–5,646 s.
La entrega progresiva está comprobada en estas muestras reales; esto no es
aceptación de ataques pendientes ni prueba universal de ausencia de errores.

**Optimización sin ataques ejecutables desplegada — 19:21 UTC:** esas
muestras aún tenían hasta 34 previews de cast rechazados y repetían el
inventario/sellado del catálogo por acción (0,3–1,1 s por sesión). El SDK ahora
reutiliza el manifest íntegro solo dentro del turno, separado por exporter,
endpoint y fight. Cada acción conserva estado completo y source guards nuevos;
el siguiente turno vuelve a verificar/provisionar el catálogo normalmente.

Un certificado nativo ligado a actor, estado y revisión identifica únicamente
ataques NPC/summon no ejecutables por tabla positiva ausente o raíces sin
metadatos obligatorios. La selección positiva usa las raíces baseline del
nivel independientemente del target y de la rama condicional de alcance;
`root_has_shape` exige esas raíces antes de aceptar cualquier cast. El puente
conserva todas las filas del repertorio y todos los datos del mapa. No infiere
incapacidad global de `twI`, ni excluye `casting:null` sin certificado. Actores
PC, nivel cero, certificados obsoletos/malformados y capacidades desconocidas
siguen abiertos para las consultas nativas habituales.

Cuando todo el repertorio está certificado como no ejecutable (o el repertorio
nativo está vacío), la exploración usa un límite adicional de pared de 100 ms,
configurable por `movementOnlySearchMs` (1–10.000). El primer movimiento sigue
requiriendo preview nativo y mantiene su oportunidad bajo el deadline total;
no se inventan movimientos ni se corta la búsqueda de hechizos desconocidos.
Esta cifra limita la exploración tras preparación, no promete un turno total
de 100 ms ni interrumpe un único trabajo nativo no cooperativo. Se omite la
máscara opcional de alcance si no existe ningún cast ejecutable certificado;
el catálogo/repertorio/mapa completos permanecen disponibles.

**129 pruebas focalizadas OK** (1,086 s): certificados válidos/ausentes,
PC/nivel cero/futuro, conservación de casts desconocidos, primer movimiento,
configuración de budget, reutilización limitada del catálogo, 6v6 Registry,
ACKs, sesiones, deadlines y máscaras. Un intento inicial de pruebas nativas
amplias activó prewarm; no hay proceso pendiente y no se acredita ese intento
como suite nativa aprobada. AI `097c14818579`, inicio 19:21:58 UTC, healthy
16/64; cinco hashes productivos idénticos al checkout. Catálogo completo
18.096 entradas, 891.900.518 bytes, manifest
`fff01f4994101780cb4bd32995dd80351871e011c014d4ca93fd82c906300218`.
La fuente live world cambió por otro despliegue a `68a6187060bb`, inicio
19:20:25 UTC; este agente no lo modificó ni reinició en esta optimización.
Evidencia: `.runtime/local/e18-no-cast-fast-path-tests.log` y
`.runtime/local/e18-no-cast-fast-path-deploy.log`. **Pendiente medir el nuevo
tiempo total en un combate real**; las cifras 2,9–5,6 s corresponden al backend
anterior y no se presentan como resultado de esta optimización.

**Fallo real confirmado — combate 67 (18:24 UTC, boot `97c40c52`):**
la corrección anterior no resolvió la entrega. Se certificó y ejecutó un move
con tres casillas a los 5,755 s del puente, pero el coordinador retenía sus
paquetes hasta agotar toda la búsqueda del turno. La segunda decisión, con
MP=0, acumuló 26,145 s de search y cerró mediante fallback a los 29,054 s.
Las 23 solicitudes HTTP sumaron 2,371 s: todavía no está identificada la
operación nativa responsable de la espera restante. Otro turno de ese mismo
combate duró 5,628 s; no debe confundirse con el fallo de 29 segundos.
Evidencia exacta por boot/fight:
`.runtime/local/e18-fight67-delayed-publication-evidence.json`.

**Corrección desplegada, movimiento básico aceptado por Hector:** el SDK publica cada
acción certificada mediante una transición privada del Registry, antes de
buscar la siguiente. Cada continuación parte del runtime adoptado y mantiene
el reloj absoluto inicial. Un claim por turno evita ejecuciones duplicadas;
el bloqueo se libera antes de entregar paquetes por sockets. Un fallo de la
siguiente acción descarta únicamente esa transacción y publica la barrera
nativa de end-turn, conservando los movimientos anteriores y los ACK reales.
La búsqueda se ejecuta fuera del bloqueo del encuentro y su adopción exige
la secuencia original: un resultado obsoleto se descarta y replantea sin
renovar el reloj. Cerrar el consumidor tras un movimiento publica la barrera
nativa para los participantes restantes. Una continuación vacía también
cierra el turno, conservando el movimiento. Con MP=0 la fracción de decisión
se aplica tras el primer preview intentado, aunque sea rechazado; con MP>0
se conserva la oportunidad de movimiento después de un cast rechazado.
Se añaden tiempos de pared/CPU por consulta nativa para aislar la espera;
operaciones/subfases son inclusivas y no deben sumarse entre sí como total.
Los diagnósticos contienen copias independientes de los contadores anidados.
La poda de `casting: null` solo aplica a filas nativas positivas cuyo catálogo
certifica que no existe una transacción de lanzamiento; `twI` no habilita esa
poda y las dependencias desconocidas siguen explícitas. No hay reglas por
monstruo ni cambios en cliente/world en esta corrección. La aceptación real
sigue abierta; no se acredita como resuelto por observar la posición interna.

**Validación y despliegue:** 117 pruebas focalizadas OK (0,698 s), incluyendo
9 de publicación compartida. La regresión 6 contra 6 utiliza Registry real,
12 actores y dos participantes de prueba: entrega MOVE antes del replanteo,
conserva ese movimiento tras un rechazo, publica end-turn y exige ambos ACKs
para liberar FIFO una sola vez. También verifica búsqueda/envío fuera del
lock, claim contra ejecución duplicada, descarte de resultado obsoleto y
cierre/continuación vacía. Es una prueba de publicación con runner de prueba,
no un nuevo benchmark de combate/hechizos nativos ni aceptación del cliente.
AI `d14f42043029`, inicio 18:40:18 UTC, healthy 16/64; cinco hashes de SDK/
planner verificados idénticos al checkout. Catálogo íntegro 18.096 entradas,
891.787.653 bytes, manifest
`af683962343093c37e95aeff4e158e047735c302b7f34f830dfebe82b4b48fe3`.
World `52ec1a12e1b3`, inicio 18:20:08 UTC, sin cambios ni reinicios propios.
El primer build intermedio se conserva por separado; el despliegue final
incluye la poda de decisión MP=0 y la adopción sin lock durante la búsqueda.
Evidencia: `.runtime/local/e18-progressive-publication-tests.log`,
`.runtime/local/e18-progressive-publication-deploy.log` y
`.runtime/local/e18-progressive-publication-final-deploy.log`.

**Prueba manual pendiente:** en el combate actual, dejar distancia y un
camino libre para el jalato, pasar turno y observar que el movimiento llega
antes de terminar la búsqueda posterior; repetir un segundo turno. Registrar
fight/boot, acción, tiempo de primera entrega y cierre. Una espera superior
al presupuesto requiere consultar `nativeQueryMetrics` para identificar
la operación concreta; el deadline sigue siendo cooperativo y estas pruebas
no demuestran todavía interrupción de un único trabajo nativo de 23 segundos.


**Corrección desplegada — combate 66 (18:09 UTC):** Jalato pasó sin moverse
con `expanded=0`, pese a disponer de PM. El repertorio nativo tardó 1,794 s,
pero la fracción nominal de decisión era solo 769 ms; la búsqueda nunca llegó
a un preview propio. No fue una predicción rival anterior al movimiento: esa
interpretación inicial se corrigió al revisar el flujo. Contexto/preparación
consumieron gran parte del turno (encoding inicial 2,388 s, sesión 4,034 s).

La búsqueda ahora puede superar su fracción nominal hasta certificar una
acción propia, conservando el deadline absoluto y la reserva de commit.
Después vuelve a aplicar la fracción normal y omite forecasting opcional si
ya no queda tiempo; el riesgo queda explícitamente desconocido. No se fuerza
un movimiento sin preview nativo ni se renueva el reloj con hints posteriores.
Regresiones: 3.575 ms de presupuesto, repertorio 1,8 s y preview 0,8 s permiten
move certificado; 1.500 ms con el mismo repertorio producen cero previews,
end_turn y ninguna acción inventada. **78 pruebas de búsqueda/sesiones/driver
OK**; integraciones nativas dependientes de hechizos no forman parte de ese
conteo. La primera ejecución amplia se interrumpió al entrar en integraciones
nativas y se conserva en un log separado, no se acredita como suite aprobada.

AI desplegada `778613ddf814`, inicio 18:18:03 UTC; hash de query_search local
idéntico al contenedor; salud 16 búsquedas/64 conexiones. Catálogo íntegro
18.088 entradas/891.608.995 bytes, manifest
`562734e4f8947f11114bf44df82dd86483177e5ad6e4b49ba955594ddf981192`.
World r19 (`dd1f5f15de34`, inicio 17:55:22 UTC) proviene de otro despliegue;
no se reinició ni modificó world en esta corrección. El combate 67 posterior confirmó
que la entrega seguía fallando, como se describe arriba. Evidencia:
`.runtime/local/e18-first-own-action-budget-pure-tests.log` y
`.runtime/local/e18-first-own-action-budget-deploy.log`.

**Regresión real abierta (combate 59, world r17):** Jalato no se mueve.
El primer turno agotó el presupuesto en `catalog_session`; el siguiente tardó
30,212 s en esa etapa (31,432 s de puente) y terminó mediante fallback.
48 solicitudes HTTP sumaron solo 0,542 s. El banco 6 vs 6 precargaba inventario
antes del reloj; por tanto no acreditaba el primer turno frío de producción.
La ruta real aún crea el exporter/inventario al turno NPC, no al inicio del
combate. Esa omisión debe resolverse y validarse sin precarga artificial.
Instrumentación por subfase implementada. El banco frío diagnóstico en r17
midió inventario **8.414 ms**, transferencia total **9.055 ms**, hash de origen
115 ms y codificación 830 ms; primer turno 10,134 s, con fallback. El siguiente
inventario tardó **336 ms**. El diagnóstico no es aceptación: SDK concurrente
y una aserción del runner limitado falló; se corrigió esa aserción sin ocultar
el alcance de dos turnos. Evidencia: `.runtime/local/e18-cold-r17-session-phases-summary.json`.

Corrección dentro de AI: el exportador vivo detecta el índice publicado por
precarga externa y restaura los hints verificados antes de volver a enumerar
TODOS los archivos; firmas completas y snapshots siguen siendo autoridades.
La búsqueda intercala rutas hacia distintos rivales, conservando todas las
alternativas. Esto no acredita que el scoring ya prefiera avanzar hacia el
jugador cuando otro rival está adyacente. **85 pruebas de regresión OK**.

Redis se evaluó con 18.078 hints reales (4,66 MB): restore local **57,5 ms**,
MGET/validación Redis **232,9 ms**, escritura **2,44 s**. No se integró porque
cuadruplicaba el restore y no evitaba la captura fría. Namespace privado de
prueba eliminado; no quedan caché Redis ni módulos temporales de este ensayo.

Catálogo completo r17 preparado sin reinicio world: 18.078 entradas,
891.288.962 bytes, manifest `d23079f6de4675bcf16f07587da2098b34baf52eb4efd4ca6c16ce73a30db501`.
**Precarga automática aplicada y desplegada con autorización explícita.**
World ejecuta `prepare_catalog_cache.py --seal` después de la precarga nativa,
antes de abrir listeners. Son ocho líneas nuevas en el arranque; se conservó
la imagen viva y todos sus otros archivos. El segundo reinicio falló por un
`sys` no importado; se corrigió, se ejecutó la sección real de arranque en un
worker Python sin servidor (catálogo frío completo: 6,04 s) y el tercer
reinicio terminó saludable. No se oculta ese fallo ni se permiten más cambios
o reinicios propios de world bajo el límite vigente.

World desplegado `e7167eff47d2`, inicio 17:39:02 UTC: catálogo completo
`9521317a154b0cabc3eb8df0a986b9f48003abee78fa3211f0e1b2c0bd753171`,
**5,27 s** en arranque, inventario **5,10 s**, antes de los puertos del juego.
Fuente viva y parche acotado coinciden por SHA; respaldo de imagen anterior
conservado. Evidencia: `.runtime/local/e18-catalog-startup-deploy/deployed.json`.
15 pruebas de preparación/caché/provisión pasan, además del arranque ejecutado.
El parche en `server/ai-service/docs/catalog-startup-review.patch` ahora es
registro del cambio aplicado, no una solicitud pendiente.

Inspección del combate real 63 (1 PC + 8 NPC, mapa 527): raíz CAS íntegra,
**12.597 celdas**, **45.902 conexiones dirigidas**, **14 alturas**;
bounds x[-266,-127], y[-125,53], z[-4,22]. El rectángulo de las posiciones
actuales contiene solo 923 celdas. El snapshot conserva esa conectividad
extensa; ocupa **1.861.098 bytes gzip / 12.079.633 bytes JSON / 146.978 nodos**.
Mapa completo exportado: 65.285 celdas/226.614 aristas; el terreno del combate
no es todo el mapa. Deben reutilizarse índices geométricos y acotarse candidatos
por capacidades certificadas, sin cortar rutas ni el contexto completo.
No se atribuye el tamaño de la arena a un error de IA ni se cambia el cliente.



Retomado por un Jalatin que no actuó. **Avance aproximado: 85 %**; sigue
pendiente aceptar el rendimiento en combate real. El código de IA queda dentro de `server/ai-service`; la única excepción
autorizada son ocho líneas de precarga en el arranque de world. Reinicios
propios de world: **3/3 consumidos**; no se harán más cambios en world.

- Combate 51, mapa 527: dos solicitudes completas tardaron **16,640 s y
  25,367 s**. La IA agotó 10 s en `session_preparation` y no llegó a mover.
  Estos registros no prueban que una sola llamada de IA durara 60 s.
- La carga SQL de autoridades/perfiles y la creación inicial del oracle
  quedaban fuera del reloj. Se implementó un plazo compartido desde la
  preparación, esperas de pool/consultas SQL acotadas y cierre del turno
  mediante la barrera nativa cuando se agota el plazo. El límite sigue
  siendo cooperativo para trabajo Python nativo síncrono.
- Se implementaron métricas por etapa y conexión HTTP persistente por turno,
  con cierre explícito, conexiones limitadas y watchdog de solicitudes.
  Medición en Docker de 100 solicitudes mínimas: mediana **0,780 ms** con
  conexión nueva y **0,318 ms** persistente; 100 aperturas frente a 1.
  Se detectó y corrigió Nagle/ACK diferidos: antes del ajuste `TCP_NODELAY`,
  persistencia costaba **42,943 ms** por petición. No mide un turno completo.
- Banco final contra AI `84d3d192931a` (inicio 16:43:40 UTC), con
  motor nativo congelado `8694975a6334`: **18.040 entradas** exportadas
  completas y selladas. World vivo coincidió con esa imagen al inicio y al
  final. Solo este agente reinició AI; los reemplazos de world fueron externos.
- El contexto compartido congelaba un grafo completo dentro del runtime y
  luego recodificaba todos sus nodos en cada snapshot. Ahora conserva ese
  mismo grafo íntegro como JSON bytes, legible por `NativeGraph`; todos los
  campos del coordinador y el mapa siguen presentes. Su preparación consume
  el mismo presupuesto de 10 s, con métrica `sharedPreparationMs`.
- Medición de solo lectura: personaje completo **179 ms**, apertura del pool
  **43 ms**. Mapa 527: **12.529 celdas y 45.660 aristas**, preparación fría
  **2,341 s** en proceso independiente. No son garantías por turno.
- Redis está activo, pero no se introduce una caché de personajes sin una
  versión de autoridad que garantice invalidación. Catálogo por contenido,
  snapshots y topología inmutable ya tienen cachés específicas. Precargar
  fuentes antes de jugar evita realizar esa preparación en el primer turno.

El alcance incluye ahora rendimiento general y máscaras de objetivos; no
reglas especiales para Jalatin. El mapa completo permanece en el puente.
Las máscaras solo excluyen objetivos fuera de un alcance superior certificado
por el resolver nativo actual, incluyendo todas las ramas condicionales y los
modificadores. Portales/áreas globales, autoridad desconocida o schemas nuevos
conservan todos sus objetivos. Movimiento y acercamiento siguen usando la
conectividad completa; rail y teletransportes no se reducen a un radio simple.

Prueba sintética de contexto compartido con 12.529 celdas/49.664 aristas:
serialización 1.945 ms → 38 ms; deepcopy 730 ms → 0,031 ms; fingerprint
94 ms → 4 ms; representación 42,18 MB → 10,14 MB. Grafo idéntico comprobado.
Son mediciones de ese componente, no del turno completo.

Backend: verificación y decodificación consumen el mismo presupuesto del
owner; las sesiones abandonadas cuyo plazo venció liberan capacidad sin
esperar los 300 s del TTL. El catálogo sellado conserva todas las referencias,
pero comprueba directamente su índice de archivos de snapshot únicos.

**456 pruebas generales OK**, 29,737 s; 13 integraciones nativas reservadas.
La suite completa anterior encontró una dependencia real del motor vivo:
Wonejo spell 7962 requiere root 361119, ausente tanto en `/app` como en el
checkout. No se fabrica esa metadata desde IA ni se ocultan esos fallos.

Validación automática de rendimiento 6 vs 6 completada; queda aceptación
en combate real. Capacidad desplegada y verificada
en `/health`: de 8 a **16 búsquedas activas** y de 16 a
**64 conexiones/hilos HTTP**, configurables en AI; sesiones y semáforos usan
el mismo límite. Prueba de concurrencia: 16 solicitudes simultáneas atendidas,
la 17.ª rechazada mientras están ocupadas y capacidad recuperada al concluir.
Esto aumenta concurrencia entre combates, no divide una búsqueda en 16 CPU.

Banco privado inicial 1 vs 1, con contexto compartido completo e invariantes
de publicación/identidad aprobadas: mapa 527 (12.529 celdas), **12,209 s**,
sin movimiento por plazo agotado; mapa 1134 (7.075 celdas), **7,832 s**, un
movimiento nativo aprobado. **No acredita aceptación**: el usuario exige ahora
pruebas **6 vs 6**, primer turno y rondas siguientes en mapas grande y menor.
Esta medición precede a la compresión interna; el banco final de 12 actores
que se describe abajo completa ambos mapas dentro del presupuesto.

Nueva compresión interna del contexto compartido: conserva exactamente los
mismos 9.877.178 bytes completos al descomprimir; ocupa 883.682 bytes y reduce
el root exterior de 23.063.056 a 11.071.728 bytes. No se omiten campos.
El primer intento 6 vs 6 terminó con código 137 antes de dejar resultados:
world fue reemplazado externamente durante la corrida (`791dd1d03974` →
`63963bddacf8`, inicio 16:36:57 UTC). No acredita aceptación ni fallo de IA.
Se renovará el catálogo completo y se repetirá con progreso por etapa,
artefacto parcial e identidad del servidor registrada. No hubo reinicio propio
de world y los contadores de memoria consultados no reportaron OOM.

Primera vuelta 6 vs 6 completada y preservada por mapa (no dos vueltas):
1134, **6 turnos NPC / 5 movimientos**, **4,497–5,884 s**; 527,
**6 turnos NPC / 6 movimientos**, **6,545–8,171 s**. Sin fallback ni errores
de source guard; ACKs privados liberados, sin acreditar un cliente conectado.
Artefacto: `.runtime/local/e18-native-6v6-one-round-result.json`. La imagen
nativa fue `63963bddacf8`, AI `84d3d192931a`; identidad estable durante esa
corrida. Un error del banco confundía alcanzar la ronda 2 con completar dos
rondas; fue corregido y la primera evidencia se conserva con su alcance real.

El siguiente intento también fue interrumpido alrededor de otro reemplazo
externo de world (`8694975a6334`, inicio 16:51:59 UTC). El banco final ejecutó
solo el CLI de pruebas en un contenedor efímero, con esa imagen nativa
congelada, SDK de solo lectura y AI real. No fue otro servidor world ni
modificó combates de jugadores.

Carga HTTP independiente: **320/320 solicitudes OK**, 16 clientes simultáneos,
mediana 2,560 ms y máximo 80,094 ms. Mide el endpoint mínimo, no búsquedas
nativas ni el comportamiento de 6 vs 6.
Resultados anteriores a continuación.

**Resultado final: 6 vs 6, dos rondas completas en cada mapa**, salida 0:

| Mapa | Turnos NPC | Mediana por turno | Máximo por turno | Movimientos |
| --- | --- | --- | --- | --- |
| 1134, 7.075 celdas | 12 | 4,27 s | 5,59 s | 6 |
| 527, 12.529 celdas | 12 | 5,24 s | 7,25 s | 6 |

Los **24 turnos quedaron debajo de 10 s**. Cada enemigo se movió en la
primera ronda; en la segunda terminó su turno. Todos consumieron la barrera
nativa privada de ACK, con 684 comprobaciones de fuente intactas e identidad
AI/SDK estable. La carga inicial del grafo en backend promedió 199 ms y
368 ms, respectivamente. Precarga nativa (61,49 s) e inventario completo
(19,01 s) se ejecutaron fuera del reloj de los turnos del banco; esto no prueba
que un primer combate frío de producción ya tenga esos datos preparados.

No hubo casts certificados: faltan metadatos nativos de casting o la autoridad
rechazó elegibilidad. Los pronósticos rivales también conservan ramas
incompletas explícitas al agotar el plazo. No se inventan acciones ni efectos.
El banco usa constructores y terreno nativos con personajes sintéticos; no
acredita admisión del registro compartido, leases de producción, callbacks
idénticos ni ACK de un cliente conectado. La mejora automática está medida;
queda confirmar el primer combate y rondas posteriores con el cliente real.

Evidencia: `.runtime/local/e18-native-6v6-frozen-869-summary.json`,
`.runtime/local/e18-native-6v6-frozen-869-data/native-6v6-roster-turns.json`
y `.runtime/local/e18-native-6v6-frozen-869.log`.



## Estado actual — 2026-10-07

**Avance aproximado: 85 %.** Base genérica implementada; aceptación manual y
rendimiento con cuatro encuentros simultáneos pendientes. Los ataques sin
implementación nativa no se inventan desde AI.

| Componente | Estado verificado |
| --- | --- |
| World | `3af10843cbc6`, inicio externo `2026-10-07T19:32:35.800276365Z` |
| AI | `26576b10f2bb`, inicio `2026-10-07T20:52:14.414608101Z` |
| Suite final | **459 pruebas OK**, motor actual `3af10843cbc6`; 169 imports nativos, ninguno externo; 116,222 s de validación de la reorganización |
| Pruebas focalizadas nuevas | 60 de búsqueda, caché, entrada y provisión OK (0,114 s) |
| Catálogo vivo | **13.269 entradas**, 711.838.483 bytes declarados en el manifiesto; sellado completo, sin faltantes |
| Reinicios propios de world | **1/3**; ninguno nuevo |

## Organización del servicio

Código en `server/ai-service/wakfu_ai/`, dividido en `planning`, `native`,
`context`, `bridge` y `http`. Pruebas en `tests/`, operaciones en `scripts/`,
mediciones en `benchmarks/`, probes Java en `tools/java/` y documentación en
`docs/`. La raíz conserva únicamente configuración, README y entradas
compatibles que ya consumen world y sus pruebas externas.

El loader estable carga la nueva entrada privada correctamente desde el
world activo; no se modificó ni reinició world. Docker arranca con
`python3 -m wakfu_ai`; `COPY .` y el catálogo completo se conservan.
**Reorganización validada: 459 pruebas OK**, 115,552 s de tests/116,222 s
de validación. Los 169 módulos nativos proceden únicamente del motor
congelado `3af10843cbc6`. Los 104 archivos Python del contenedor AI coinciden
por SHA con el SDK actual; servicio saludable y catálogo sellado completo.
No se modificó el algoritmo, los presupuestos ni el soporte de hechizos.
Evidencia: `.runtime/local/e18-ai-package-layout-final-full-suite.log` y
`.runtime/local/e18-ai-package-layout-final-rebuild.log`.

Estructura y comandos vigentes: [README del servicio](../../../server/ai-service/README.md).

El catálogo completo se prepara antes de dar AI por listo. Una caché privada
persiste snapshots por contenido y firmas de archivo; cada turno sigue
inventariando todas las rutas y detectando cambios. No se recortan datos.
La preparación inicial del catálogo pasó de varios segundos a 0,806 s en
el ensayo individual preparado; esta cifra no es una garantía por turno.

La ordenación de todas las celdas y la preparación de rutas se contabilizan
como preparación de contexto, conservando los límites reales del turno.
El presupuesto predeterminado es **10 s por turno completo**; las consultas
nativas y el cierre cooperativo pueden superar unas décimas ese plazo.

Ensayo nativo terminado sobre la imagen actual, con motor precalentado como
el arranque real, catálogo frío del proceso y NPC inicialmente a distancia.
Contexto íntegro: 7.075 celdas y 24.556 aristas. Fracción de búsqueda **0,25**,
seleccionada para producción tras mejorar respecto al ensayo preparado 0,5.

| Encuentros simultáneos | Ataques | Movimientos | Tiempo por turno |
| --- | --- | --- | --- |
| 1 | 2/2 | 2/2 | 6,788–7,052 s |
| 2 | 4/4 | 4/4 | 7,745–8,071 s |
| 4 | 6/8 | 8/8 | 8,134–9,686 s |

Sin fallback ni fallos de invariantes. Son 14 turnos privados, no una garantía
de latencia ni aceptación en cliente. Con fracción 0,5, el ensayo preparado
anterior consiguió 2/2, 4/4 y 1/8 ataques. Evidencias:
`.runtime/local/e18-native-prepared-flat-owner-live-turns.json` y
`.runtime/local/e18-native-prepared-quarter-search-owner-live-turns.json`.

El encoder y lector fragmentados están implementados y probados, pero su
activación fue descartada por rendimiento: el ensayo nativo produjo ataques
1/2, 4/4 y 0/8, con un máximo de 23,593 s. Permanece desactivado.
Evidencia: `.runtime/local/e18-native-parts-owner-live-turns.json`.

El primer Wonejo que pasó por timeout fue reproducido y se corrigió la
preparación del catálogo. Sigue pendiente repetir una pelea real nueva y
confirmar el primer turno. La prueba general está al final de este documento.

**Cierre de esta fase por la instrucción del usuario de detenerse cuando el
siguiente avance deje de ser rentable sin los hechizos.** La base genérica queda
desplegada; no se añaden comportamientos ni efectos especulativos. Retomar
roles y balance con repertorios nativos nuevos. La aceptación manual y el
rendimiento con cuatro encuentros siguen pendientes: no se considera E18
completo. La suite final terminó en el proceso49315; evidencia:
`.runtime/local/e18-ai-prepared-search-current-world-full-suite.log`.
Reconstrucción y provisión final: proceso84281 terminado exit0,
`.runtime/local/e18-ai-final-quarter-search-rebuild.log`. Revisiones anteriores:
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

1. Suite final y despliegue verificados: 459 pruebas OK, 60 focalizadas OK,
   AI saludable; hashes de búsqueda, entrada, puente y provisión iguales al SDK.
2. Confirmar una pelea manual completa: primer turno, acercamiento, ataque,
   muerte de un enemigo, resultados y segundo encuentro sin memoria obsoleta.
3. Dejar documentada la limitación de concurrencia: 6/8 ataques con cuatro
   encuentros no acreditan aceptación completa ni un SLA.
4. Retomar corpus real de roles y balance cuando existan más hechizos nativos.
   Los nuevos repertorios entran automáticamente; no ampliar el puente ni
   añadir reglas por monstruo para suplir ataques ausentes.

El formato fragmentado tiene encoder, lector y transporte completos, pero
queda **desactivado** tras empeorar el ensayo nativo. No es un pendiente de
activación ni una razón para prolongar esta fase.

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
