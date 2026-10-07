# IA táctica Wakemu — E18

Estado actualizado y evidencias: [README de E18](../../../docs/soluciones-wakemu/E18-ia-tactica-enemigos/README.md).

Servicio de búsqueda determinista por arquetipos y capacidades, sin Laya ni
reglas por especie. El SDK completo vive aquí; world lo monta en lectura y
mantiene únicamente el puente genérico y la autoridad de ejecución.
El servicio recibe catálogos, runtime, autoridades y campos futuros completos,
solicita previews nativos y decide. No inventa ataques sin soporte nativo.

Validación final: **459 pruebas OK** sobre el motor vivo `3af10843cbc6`.
Benchmark: ataques 2/2, 4/4 y 6/8 con 1, 2 y 4 encuentros; aceptación manual
y carga completa pendientes.

Presupuesto predeterminado: **10 s por turno completo de IA**; fracción de
búsqueda 0,25 para reservar ejecución y decisiones posteriores. La preparación
completa del catálogo se provisiona y sella al reconstruir AI; snapshots e
índice privado se reutilizan comprobando las firmas de todos los archivos.
`rebuild.sh` reconstruye y reinicia solamente AI a partir de la imagen viva
de world, conserva `COPY .` y provisiona su catálogo completo.

Formato fragmentado experimental implementado pero desactivado: el ensayo
nativo empeoró la latencia. La ruta productiva usa snapshots completos planos.

## Responsabilidades

World autoriza repertorio, nivel, uso, recursos, condiciones, LOS, orientación,
terreno y efectos. Genera previews aislados con RNG independiente y claves que
incluyen todos los campos relevantes (estados, cooldowns, usage, XYZ, dirección,
ocupación, recursos y versiones). La IA busca sobre ese grafo de transiciones:
no crea hechizos, calcula daños nativos, interpreta IDs Dofus ni supone LOS plano.

Se reutiliza el patrón de búsqueda de Dofus, no su simulador. El grafo recibido
permite mover → lanzar → retirarse y múltiples casts con sus estados intermedios.
Los límites de profundidad/nodos/tiempo y las visitas por ruta impiden bucles de
coste cero. La poda por clave mantiene separados estados con usos distintos;
la diversidad del beam conserva intenciones/blancos antes de completar por score.

La respuesta es indicativa: world ejecuta **solo la primera acción**, verifica
`stateKey`, revisión, actor actual y propiedad/uso nuevamente, confirma el commit,
entrega su bloque FIFO y solicita otra decisión. La barrera `13510` es de
fin de turno, no ACK por ataque; el protocolo actual no acredita ACK individual. Nunca reproduce una cola tras una reacción.
El servicio no confirma reservas al elegir un plan. World lleva el blackboard
confirmado en cada petición; esto permite múltiples réplicas sin memoria privada
incoherente ni una segunda autoridad de combate.

## HTTP

- `GET /health`: estado y `protocols: [1,2,3]`; conserva `protocol: 1`.
- `POST /v1/decide`: protocolo 1 histórico o protocolo 2 explícito.
- `POST /v2/decide`: exige protocolo 2.
- JSON mal formado, claves duplicadas, NaN/Infinity, contratos inválidos: 400.
- Cuerpo máximo 4 MiB: 413; lectura con timeout: 408.
- Máximo ocho decisiones simultáneas por proceso: 503 al saturarse. Este límite
  cubre decisiones; el servidor HTTP de desarrollo usa threads por conexión.

No hay logs de snapshots. Las trazas vuelven en la respuesta, sin datos de cuenta.

## Protocolo 3: consultas nativas y contexto completo

El juego usa el SDK de este directorio mediante un único puente genérico de
world. El catálogo del world vivo y el runtime completo se transportan como
grafos por hashes y bloques: el límite por frame no recorta el tamaño total,
monstruos, habilidades, mapas, actores ni campos futuros. El Dockerfile copia
el SDK entero con `COPY . /app`; `rebuild.sh` reinicia solo AI.

- `/v3/context/status`, `/v3/context/block` y `/v3/context/manifest`: provisión
  por contenido, bytes congelados y verificación SHA de todo el manifiesto.
- `/v3/decide`: negociación de una consulta nativa cada vez, ligada a
  `requestId/sourceKey/rootState`, con guard de fuente en el dueño del combate.
- `/v3/cancel`: libera la búsqueda suspendida, idempotente y ligada a fuente.

Operaciones del SDK: `state`, `repertoire`, `preview`, `line_of_sight` y
`project_turn`. El repertorio incluye todas las habilidades propias y metadatos
nativos; consultas no soportadas devuelven sus dependencias explícitas.

Cada preview aporta `key/nativeContext` como hash del grafo completo. Ese grafo
conserva también `transition`: fuente, acción, paquetes binarios y transacción
íntegra con sus campos futuros. `transaction.fight` comparte la referencia con
`runtime.fight`. `transitionContext` apunta al mismo grafo; la publicación se
identifica como `uncommitted_native_preview`. Los paquetes son evidencia de
simulación y nunca se envían al cliente desde este recibo.

`runtimeIdentity` identifica runtime/autoridades/flags completos sin incluir
el recibo. La búsqueda y el pronóstico deduplican con esa identidad dentro de
la sesión, pero las consultas recuperan el estado por `key`. La identidad no
es permiso de ejecución ni se reutiliza entre encuentros. La primera acción
seleccionada requiere certificación fresca y commit nativo con entrega FIFO.

El recibo conserva en `damageContexts` el contexto completo del callback nativo
de daño, junto con efecto, invocación, plan y actores congelados en ese instante.
`damageContextEvidence` distingue la localización observada FRONT/BACK/SIDE de
la localización que aplica el efecto cuando deshabilita ese modificador.
La decisión conserva esas observaciones en `orientationEvidence`; no añade
una ventaja de daño por orientación o altura. La geometría `nativeFacings`
conserva diversidad de posiciones en el beam, sin alterar sus puntuaciones.
Los corredores
confirmados proceden de probes LOS nativos y la utilidad de posición utiliza
la topología XYZ dirigida; los resultados de los previews deciden la utilidad.

Cuando otro aliado vivo tiene HP faltante, `nativeSupportApproach` mide la
distancia dirigida XYZ hasta ese conjunto de aliados. No afirma alcance,
LOS, coste ni legalidad de una curación. Las rutas hacia enemigos y aliados
heridos se intercalan sin eliminar candidatos ni prefijos. Con beam de al
menos dos ramas se conserva, además del mejor resultado global, una posición
que mejora esa distancia para explorar su continuación. Solo el preview
nativo de la habilidad puede producir utilidad de curación o protección.
Esto funciona aunque la capacidad todavía no haya sido observada porque
el cast esté fuera de alcance en la raíz. No garantiza posiciones laterales
que abren LOS sin reducir distancia ni protección sobre aliados con HP lleno.

Protocolo 3 también acepta `policy.featureWeights` y `outcomeFeatures` en la
descripción de la raíz y en cada resultado de estado/preview. Solo un
`NativeOracle` (o `run_turn(..., outcome_features=provider)`) configurado
explícitamente con un provider de mediciones puede
emitir esas features; el provider recibe una copia profunda del runtime
completo, devuelve valores acumulados y queda incluido en las autoridades e
identidad fuente. El SDK rechaza si el provider muta esa copia y compara la
fuente viva antes/después para detectar efectos externos. El provider debe ser
puro. Su configuración debe vivir en el objeto callable, dueño enlazado,
closure o argumentos por defecto, que forman parte de la identidad; no debe
depender de globals mutables externos. El SDK no infiere utilidad leyendo
campos desconocidos del grafo nativo. Nombres y límites numéricos son los mismos
de protocolo 2.
Una feature ponderada solo puntúa cuando existe una medición tanto en raíz
como en el preview: se usa `valorPreview - valorRaíz`. Si falta cualquiera, no
se asigna cero ni una ventaja o penalización; la respuesta añade la dependencia
`outcome_feature_missing_root:<nombre>` o
`outcome_feature_missing_state:<nombre>`. Las features sin peso no cambian el
ranking. Las reglas/documentación de features para el DTO precomputado de
protocolo 2 permanecen sin cambios.

`NativeSession.decide()` conserva la certificación fresca por defecto. El
driver usa `decide(certify=False)` para el commit inmediato: comprueba otra
vez la fuente después del borrador de coordinación y llama al commit nativo
transaccional, que valida la acción antes de preparar/adoptar la entrega.
No reutiliza el estado del preview ni ejecuta la cola de un plan antiguo.

Las distancias reutilizan solo la adyacencia derivada de `ImmutableTerrainSet`
validado, conservando todas las celdas/aristas y recalculando ocupación y
objetivos en cada estado. Terreno mutable o de tipo personalizado se recorre
otra vez. El encoder JSON reutiliza su configuración por grafo, manteniendo
los mismos bytes y referencias completas de cada nodo.

## Petición protocolo 2

Conserva los campos de protocolo 1: `requestId`, `stateKey`, `fight_id`,
`actor_id`, `current_id`, `walkable` (XYZ), `edges` (pares XYZ dirigidos), `actors`.
Añade `fightInstanceId` (UUID/identidad estable del encuentro), `turnId`,
`stateRevision` (enteros no negativos), `catalogVersion`, `policyVersion`,
`rootState` y `states`.

Cada actor contiene `id`, `team`, `controlled`, `position`, `hp`, `max_hp`, `armor`,
`ap`, `mp`, `wp`. Puede incluir más contexto JSON nativo: dirección, estados,
características y usage; la IA no lo reinterpreta. El roster del nodo raíz debe
coincidir exactamente con los actores de la petición, incluyendo ese contexto.

Cada nodo:

```json
{
  "key": "hash-completo-del-estado",
  "actors": [],
  "threat": 0,
  "positionValue": 0,
  "uncertainty": 0,
  "transitions": [{
    "id": "accion-estable-en-este-nodo",
    "supported": true,
    "action": {
      "type": "cast", "spellId": 7962, "level": 10,
      "targetId": 1, "target": [2, 0, 0]
    },
    "nextState": "hash-del-preview"
  }]
}
```

`actors: []` arriba es abreviatura del esquema; un nodo real necesita su roster.
Los actores existentes se conservan incluso muertos, con HP cero. Se permiten
actores adicionales creados por una invocación nativa. La creación no recibe una
utilidad ficticia: hace falta forecast posterior/valor de posición acreditado.
Un máximo de 2048 nodos, 8192 transiciones, 32768 registros de actor en total.

Acciones admitidas:

- `{"type":"move","path":[[1,0,0],[2,0,1]]}`: ruta XYZ completa;
  validación adicional de aristas cardinales, ocupación, PM y destino previsto.
- `{"type":"cast","spellId":7962,"level":10,"targetId":1,"target":[2,0,0]}`:
  `targetId` opcional/nulo para celdas; legalidad certificada por preview world.
- `{"type":"end_turn"}`. Siempre hay alternativa sintética de terminar sin actuar.

Sin acción `face`: no hay giro gratuito. Las reacciones de movimiento forman
parte de los previews. Una ruta interrumpida se expresa mediante su prefijo real.
`supported:false` descarta la transición sin evaluar efectos parcialmente
conocidos. Su motivo puede conservarse en campos de evidencia del productor;
la traza informa cuántas transiciones fueron descartadas.

`threat` es daño/riesgo esperado del siguiente turno rival, obtenido por world.
`positionValue` resume ventajas nativas demostradas (tiro, salida de zona,
corredores); no añade premios por Z ni orientación. Si faltan esos campos, valen
cero: la decisión compara consecuencias inmediatas y **no acredita** análisis de
amenazas/espalda/altura. El mejor backstab procede del mayor daño de su preview.
`uncertainty` penaliza previsiones incompletas; efectos obligatorios sin soporte
se excluyen completamente mediante `supported:false`.

Un productor también puede enviar `rivalForecasts` en cada estado, en lugar de
`threat`. El servicio compara planes de respuesta certificados de cada rival:

```json
{"rivalForecasts":[{"actorId":1,"mode":"approximate",
 "unknownDependencies":["future_turn_lifecycle_not_projected"],
 "plans":[{"id":"response-1","supported":true,"steps":[
   {"action":{"type":"cast","spellId":100,"level":1,"targetId":-2,
              "target":[0,0,0]},"actors":["roster completo posterior al cast"]}
 ]}]}]}
```

El ejemplo abrevia `actors`; en una petición real contiene los mismos objetos
de actor completos que un estado. `rootActors` opcional fija el roster después
de una proyección del comienzo del turno rival; world certifica esa proyección
y cada paso. El servicio comprueba identidad/equipo, acciones tipadas, rutas,
ocupación y presupuesto PM; propiedad, límites de lanzamiento, PA/PW, efectos
y lifecycle siguen siendo autoridad del motor. No ejecuta las respuestas.

`mode:native` identifica pasos certificados por el motor; `approximate` exige
dependencias desconocidas explícitas. Ninguno garantiza un futuro exacto ante
azar o decisiones de jugadores. La traza conserva modo, dependencias, plan
elegido y riesgo. Se usa **el máximo de los planes alternativos de cada rival**,
y se suman esos máximos como estimación independiente: no representa un turno
conjunto legal, ni elimina solapamiento entre víctimas de rivales distintos.
El riesgo considera deltas netos de HP, armadura, bajas y recursos aliados
perdidos con los pesos configurados; el coste de lanzar del enemigo no se
cuenta como amenaza. El peso `threat` aplica después sobre esa utilidad adversa.

Todos los estados deben cubrir los mismos rivales vivos seleccionados en el
root; un rival muerto desaparece. No omitir previsiones de una alternativa para
hacerla parecer segura. Límites globales:512 pasos/8192 registros de actor por
petición;16 rivales,16 planes/rival,16 pasos/plan. Planes `supported:false` se
descartan completos. El productor activo de world todavía no envía este campo:
este contrato amplía el servicio y su corpus, sin atribuirlo al juego desplegado.

`teamContext`, opcional, es checkpoint confirmado:

```json
{"fightInstanceId":"encuentro-uuid","stateRevision":4,"team":1,
 "focusId":1,"reservedCells":[[2,1,0]]}
```

La identidad, revisión y equipo deben coincidir. Foco muerto/amigo es inválido.
La preferencia de foco es pequeña (5% del daño efectivo al foco); ocupar una
reserva resta 5 unidades de coordinación. Son preferencias, no prohibiciones.
World debe expirar/reconstruir las reservas al actualizar la revisión/encuentro.

## Evaluación y política

Utilidad = daño enemigo neto + curación aliada neta + armadura neta ponderada
+ bajas − pérdidas aliadas + control de recursos rivales + recursos aliados
+ mejora de amenaza/posición + coordinación − incertidumbre.
El HP perdido propio/friendly fire resta utilidad. El daño sobre muerto y la
sobrecuración no se suman: se usan deltas HP de previews, acotados por max_hp.
Una etiqueta de rol no obliga a curar ni huir; la intención se deriva del resultado.
No se puntúan efectos de estado sin deltas o features de resultado acreditados.

`policy` admite `weights` y estos límites enteros:

| Campo | Inicial | Máximo |
|---|---:|---:|
| depth | 4 | 16 |
| beam | 12 | 64 |
| nodes | 576 | 4096 |
| budgetMs | 50 | 250 |
| alternatives | 6 | 16 |

Pesos iniciales: damage/healing/position/threat/coordination/uncertainty=1,
armor=.25, kills=25, control=.5, resources=.1. Se admiten pesos 0..1000.
Son parámetros iniciales, **no balance validado en partidas**. World puede cargar
la política versionada desde DB y enviarla; el servicio no consulta SQL por nodo.
El deadline incluye validación del DTO y detiene la expansión, pero no interrumpe
la validación ya iniciada. Los límites de tamaño y cardinalidad acotan esa fase.
Si expira, devuelve la mejor opción ya evaluada o termina; world sigue necesitando
su timeout de transporte y límite total de turno.

## Respuesta

Devuelve protocolo, IDs, revisión y versiones originales; `decision` contiene
`actor_id`, `actions`, `intent`, `target_id`, `score`, `score_components`,
`transitionIds` y `reason`. `trace` incluye expansiones, latencia, deadline,
límite de nodos, descartes sin soporte y alternativas por intención/blanco.
Empates: mayor score, menos acciones, IDs de transición ordenados. Con el mismo
DTO/política y búsqueda completa, el resultado es determinista. Un deadline
agotado puede explorar prefijos distintos según carga; no se promete idéntico
resultado bajo timeout. El grafo y los previews son responsabilidad de world,
no prueba de legalidad suficiente para confiar en una respuesta del servicio.

## Prueba general reproducible

Desde la raíz del repositorio:

```sh
PYTHONPATH=server:server/ai-service python3 -m unittest discover -s server/ai-service/tests -p 'test_*.py' -v
PYTHONPATH=server:server/ai-service python3 -m unittest tests.test_ai_service tests.test_combat_ai tests.test_combat_ai_client
```

Prueba HTTP completa sin reiniciar world:

```sh
WAKFU_AI_BIND=127.0.0.1 WAKFU_AI_PORT=18091 python3 server/ai-service/wakfu_ai/http/server.py
```

En otra terminal:

```sh
curl --fail http://127.0.0.1:18091/health
python3 server/ai-service/scripts/acceptance.py --url http://127.0.0.1:18091
```

Esperado: health con protocolos 1/2 y aceptación que verifica movimiento
histórico, secuencia mover/lanzar/retirarse, remate, curación útil, friendly fire,
rechazo de contratos obsoletos/acciones sin soporte y límites HTTP. Termina con
`Aceptación HTTP completa: OK`. Detener el proceso con Ctrl-C.
Los casos usan previsiones de prueba, no acreditan su fidelidad al motor nativo.
El puente inicial está activo en world; consultar `PRUEBA-WORLD.md` para la
aceptación de juego. Avisar al usuario antes de cualquier nuevo reinicio.

## Extender con ataques y mecánicas pendientes

Separación de módulos:

- `planner.py`: compatibilidad v1 y dispatch de versiones.
- `tactical.py`: contrato y `ForecastAdapter` para estados certificados.
- `search.py`: búsqueda genérica con adaptador y callback de evaluación inyectados.
- `scoring.py`: utilidad de consecuencias; no contiene IDs de habilidades.
- `capabilities.py`: valida etiquetas combinables y expone afinidades de rol
  en la traza; no cambia las reglas ni la puntuación de consecuencias.
- `server.py`: transporte y límites de operación.

Para dar de alta cualquier ataque nuevo, el motor nativo implementa/valida su
efecto, el productor añade sus transiciones legales y el servicio compara sus
deltas. No hace falta registrar el ID en la IA. Daño, cura y armadura entran por
los deltas existentes, incluso cuando la habilidad combina varias capacidades.

Para una mecánica nueva que no se refleja en HP/recursos, world puede enviar
features adicionales con evidencia en su preview:

```json
{
  "outcomeFeatures": {"glyph_control": 10, "ally_escape_routes": 2},
  "policy": {"featureWeights": {"glyph_control": 0.5, "ally_escape_routes": 1}}
}
```

En la petición real, `outcomeFeatures` va **dentro de cada nodo** y `policy` en la
raíz. Cada feature es una medición acumulada en la misma escala; la evaluación
usa `valor_del_nodo - valor_de_raíz`. Nombres snake_case (hasta 64 caracteres),
máximo 64 features/pesos; valores finitos ±1e9, pesos finitos ±1000. Los pesos
son parte de `policyVersion` y las mediciones de la clave completa del estado.
Una feature sin peso no añade utilidad. Las features valoradas aparecen como
`feature:nombre` en el desglose; su intención puede seguir siendo `position`
si no hubo deltas HP/armadura/control. No duplicar en features la misma ventaja
ya contabilizada por otra componente.

Esto permite añadir invocaciones, glifos, buffs, debuffs o mecánicas de boss sin
cambiar el buscador. No acredita que el motor ya ejecute esas mecánicas: una rama
obligatoria no implementada continúa `supported:false`. La utilidad de features
la suministra world con evidencias, nunca se deduce del nombre del ataque.

Para sustituir el grafo precalculado por previews bajo demanda, implementar los
cuatro métodos del adaptador (`state`, `legal_actions`, `preview`, `terminal`) y
pasar un callback de score a `bounded_search`. Los previews deben ser aislados,
con cancelación/deadline respetados. El contrato de search espera IDs de estado
completos y transiciones tipadas, y no depende de catálogos o clases de combate.

## Repertorios y diversidad de candidatos

World clasifica los árboles nativos con etiquetas combinables: daño, cura,
armadura, control, desplazamiento, buff, debuff, invocación y área. Dependencias
desconocidas y ciclos quedan explícitos. Un mismo hechizo puede pertenecer a
varias capacidades; no se asigna un rol fijo por especie ni ID.

`capabilities` es una lista opcional en la raíz del DTO, con `spellId`, `level`,
`minimum`, `maximum`, `tags`, `conditional` y `unknownDependencies`. Los rangos
son el envolvente de tablas nativas condicionales, no un permiso de lanzamiento.
La respuesta expone `trace.roleAffinities` para diagnóstico.

El productor intercala candidatos de cada hechizo y movimientos; conserva
sucesores variados por acción/hechizo/blanco para la segunda profundidad.
Prioriza aliados heridos para cura y rivales para daño, pero conserva blancos
alternativos para efectos mixtos. La aproximación busca alcance útil; un sanador
sin aliados heridos no recibe recompensa por acercarse al enemigo. Las
consecuencias nativas siguen decidiendo la utilidad final. Los casos de sanador
y atacante a distancia se verifican con fixtures, porque esos ataques aún no
están exportados en el catálogo NPC ejecutable.

## Políticas durables por encuentro

La migración `045_ai_tactical_profiles.sql` define `ai_policy_versions`,
`ai_policy_active` y `monster_ai_profiles`. El perfil global inicial es
`normal`, versión 1. Sus límites son 48 previews, 150 ms y profundidad 2;
los pesos por defecto pertenecen al servicio. La dificultad cambia pesos y
presupuestos; no modifica HP, daño base ni recursos de los monstruos.

El SDK de `ai-service`, ejecutado mediante el puente estable, lee en una
transacción todos los perfiles y bindings completos cuando el encuentro
solicita IA por primera vez. Los bindings asignan arquetipos reutilizables,
sin reglas particulares por monstruo; solo puzzles explícitos admiten
excepciones de mecánica. Congela esos valores
en el runtime del encuentro: una edición DB afecta encuentros nuevos. El hash,
nombre y versión se incorporan a `policyVersion` y al contexto de validación.
No consulta la DB por preview ni importa el buscador dentro de world.

Publicar un perfil nuevo exige insertar una nueva versión y cambiar el binding
activo o el de referencia. Se validan límites, nombres, pesos finitos y campos
conocidos antes de usarlo. Una política inválida termina el turno NPC con evento
`combat_monster_tactical_policy_rejected`; no aplica efectos parciales.

Ejemplo SQL (emulación de dificultad, no cambio de reglas nativas):

```sql
BEGIN;
INSERT INTO ai_policy_versions(profile,version,policy,forecast_limits)
VALUES ('careful',1,
        '{"weights":{"threat":1.5,"coordination":1.2},"beam":16}',
        '{"max_previews":64,"budget_ms":200,"depth":2}');
UPDATE ai_policy_active SET profile='careful',version=1 WHERE singleton;
COMMIT;
```

La ponderación de amenaza requiere una medición provista por world; el valor
actual del puente no acredita previsión de ataques del siguiente turno rival.
Aumentar ese peso por sí solo no crea dicha previsión.

## Arenas y presupuesto de transporte

El protocolo 2 admite 32767 celdas y 131068 aristas nativas; el protocolo 1
conserva 8192/65536. Se mantiene el máximo de 4 MiB por petición usando JSON
compacto. El límite corresponde al tamaño del DTO completo, no de cada nodo.
World reutiliza por hash la topología inmutable para claves y rutas; los
fixtures mutables siguen serializando el estado completo para detectar cambios.
La búsqueda de proximidad termina en la primera posición con alcance útil.

`budgetMs` limita la búsqueda tras validar el DTO. La traza separa
`validationMs`, `searchMs` y `elapsedMs`; validación y HTTP no se presentan como
parte del límite de expansión. World tiene su presupuesto separado de previews.

El proceso HTTP admite 16 conexiones en curso y 8 decisiones simultáneas. Las
conexiones excedentes reciben 503; cabeceras/cuerpos incompletos tienen timeout
de 5 s. La prueba `test_http.py` acredita saturación y recuperación de slots.

En las peticiones del puente, `terrainScope=certified_action_footprint` indica
que `walkable/edges` es el subconjunto exacto requerido por las acciones
certificadas: posiciones de todos los actores de todos los nodos, destinos de
cast y cada paso de las rutas. Las aristas se filtran del grafo nativo completo.
World genera los previews con la arena completa y su hash conserva ese terreno;
la IA no busca rutas nuevas ni extrapola conectividad fuera del subconjunto.
`producerTrace.nativeCells/decisionCells` permiten comprobar la reducción.

La lista de movimientos preserva opciones FRONT/BACK/SIDE según la función de
orientación nativa, incluso si una ruta frontal más corta llenaría la shortlist.
No hay premio por etiquetas: una espalda que no mejora consecuencias pierde
frente a la acción más barata. Las ocho direcciones se verifican en fixtures.


### Presupuesto v3 de búsqueda y del turno

`policy.limits.budgetMs` cuenta trabajo local de exploración: el reloj se
pausa mientras el generador espera la respuesta de una consulta nativa.
La lectura y validación completas del contexto de cada continuación también
se separan del trabajo de exploración. Se registran como
`searchBudgetEvidence.contextPreparationMs`; generación de candidatos y
evaluación siguen consumiendo el presupuesto local.
No pausa el plazo real impuesto por el SDK. `nativeBudgetMs`, opcional en
contexto y respuestas nativas, transmite la duración restante del dueño;
el servicio usa ese dato como límite conservador. No concede autoridad
para ejecutar tarde. `policy.commitReserveMs` reserva500ms por defecto
para certificación y commit; valores enteros entre0 y10000. El pronóstico
rival mantiene su presupuesto de tiempo total y se acota por esa reserva.
La respuesta incluye `searchBudgetEvidence.nativeWaitMs` y la reserva.
`policy.searchTimeFraction` (0 < valor ≤ 1; defecto 0,5) fija, con el primer
hint del propietario, una fracción del tiempo restante después de esa reserva
para esta decisión. Incluye preparación, consultas y pronóstico rival. Los
hints posteriores pueden reducir el plazo del propietario, pero no renovar
la fracción de búsqueda. Sin hint no se añade este límite. La traza expone
`decisionWallBudgetMs` y `searchTimeFraction`. La mejor acción certificada
se conserva al terminar; cada acción real sigue requiriendo certificación y
una decisión nueva desde el contexto actualizado.
Esta corrección está en validación: no confundir sus regresiones con
aceptación HTTP ni pruebas completas del cliente.

### Catálogo completo congelado por versión

`/v3/context/seal` verifica y copia todos los blobs y el manifiesto a un
archivos privados de solo lectura, sin filtros ni límite de tamaño total.
Conserva todas las rutas alias y verifica los hashes durante la copia.
Las versiones posteriores reutilizan los bytes congelados de hashes ya
presentes y copian únicamente los nuevos en un delta privado; el mapa de
cada manifiesto conserva todas sus entradas. Los archivos originales del
CAS no se toman como válidos por estar en ese mapa: sus APIs siguen
recalculando el hash completo. Sellados repetidos y nuevas versiones
comprueban la identidad de cada archivo privado que utilizan.
La publicación ocurre únicamente cuando el catálogo está completo. Las
sesiones posteriores reutilizan esa versión congelada; los contextos
dinámicos siguen verificándose íntegramente. `read_catalog` comprueba la
identidad del archivo privado antes y después de leer; los métodos del CAS
original siguen calculando hashes para detectar cambios en sus archivos.

Ensayo3476 (`--cold-catalog`, motor prewarm como en arranque world)
terminado exit0: **2/2 turnos con movimiento y ataque7962**, daño5 en ambos,
sin fallback ni fallos de invariantes. Tiempos9,209–9,693s; preparación
de catálogo primera4,630s, segunda inferior. Evidencia:
`.runtime/local/e18-native-cold-catalog-owner-world-live-turns.json`.
Se pidió repetir pelea nueva y comprobar primer Wonejo; aceptación manual
todavía pendiente. No reinició world.
