# Orden nativo de bloques y snapshots de combate

Investigación del incidente Cuerbik, actor32/fight597143844, 2026-10-05
01:01UTC. Los registros privados permanecen en `.runtime/local/`.

## Evidencia y límites

La captura recibió Puño13509 y daño12613, luego13420, snapshots12873 y otro
13420. El cliente mostró−71 tierra y erroraES:115 de finalización cruzada de
scripts. El socket terminó conEOF; ninguna prueba atribuye ese cierre al error
ni acredita un paquete de victoria en la ventana final.

`ProbeNativeDamageSnapshotOrder` usa bje1153/nivel72, su manager de
características real, cuU12873 capturado, descriptor NPCeHj, ffh y consumo eXt.
Instalar HP15 antes de consumir71 lleva a0; consumir71 sobre86 y después instalar
snapshot15 conserva15. Es una prueba del orden hipotético perjudicial. El
receptor gráfico completo inicia JOGL y no se ejecutó en este probe offline.

**Ese resultado no prueba que el cliente real siga ese orden.** cjU.a(cuU)
crea una accióncjV y la añade a aUb; el descriptor se aplica en cjV.cby, no al
recibir inmediatamente el paquete. cjU termina el bloque con aUb.m.

13420=cvG; cjq.a llama aUb.Ac(fight), que llama aER.cbu. El bloque se añade a
una FIFO. aER.cbv no inicia el siguiente mientrasdIJ sea verdadero; el callback
local aEP.b(aEO), al finalizar el bloque, libera el siguiente. Este camino no
emite ningún ACK de red.

13852=csR; ckG procesa movimiento de actores del mundo. No es un ACK de efectos.
13510 es la sincronización de fin de turno ya implementada; no acredita una
sincronización para cada lanzamiento.

`ProbeNativeActionBlockOrder` prueba los originales aER/aEV sin gráficos ni
red: una acción retenida inicia, el bloque siguiente de snapshot no corre, y
sólo al llamar cbh corre el snapshot. La cola queda vacía. ResultadoPASS.

Por tanto no se modifica la transmisión para esperar un ACK inventado ni se
omite HP basándose únicamente en la llegada temprana del snapshot. Sigue
pendiente probar si una ruta concreta de script/efecto finaliza antes de aplicar
su daño, o si existen dos aplicaciones del mismo efecto en la ejecución real.

## Reproducción

Compilar ambos probes con JDK22 y classpath `client/lib/*`. Ejecutar
`ProbeNativeDamageSnapshotOrder` con el payload12873 completo del NPC; ejecutar
`ProbeNativeActionBlockOrder` sin argumentos. El snapshot privado no se publica.

## Causa concreta posterior: identidad repetida de acciones

La captura Puño227/228 usa el mismo segundo entero del headercvB para13509 y
12613. Es `cbc()`, la identidad de una acción de la cola, **no** la identidad
que agrupa todos los paquetes de un request.

El recurso original `eFx.pun[219]=8000` selecciona `8000.lua` (Poing). Su
`applyEffects()` llama `ScriptedAction.executeAllAction(3, efectos[i])` para los
tipos1,2,3,4,5,1015. El consumidor originalaFl ejecuta aEO.a(effect,false) en un
bucle mientras cQ encuentra esa acción. aEV elimina la acción porxX(cbc), que
busca la primera identidad igual, no por identidad del objeto.

`ProbeNativeForcedActionIdentity` reproduce esa ruta de eliminación en el
originalaEV: con animación ya iniciada y amboscbc228, la primera ejecución
forzada elimina la animación y deja el efecto. El bucle vuelve a ejecutar el
mismo efecto: dos ejecuciones. Concbc228/229, ejecuta el efecto una vez y deja la
animación intacta. Resultado2PASS. No ejecuta Lua/gráficos; la llamada del script
se acredita además con el recurso original y el consumidor originalaFl.

`ProbeNativeCrossScriptCompletion` reproduce exactamente el diagnósticoaES
`script(2)` finalizado desde `script(4)`. El callback original registra ese error
pero **también completa la acción**. El probe inicializa sólo la identidad y la
lista de observadores del objetoaEp medianteUnsafe para evitar LuaJNI; el
método de finalización original no se reemplaza. Este resultado acredita el
riesgo de callback cruzado al reiniciar una acción, no la causa delEOF.

## Corrección común y contrato de integración

`ExportNativeActionPackets` exporta reproduciblemente los descendientescvB de
`wakfu-client.jar` a `server/protocol/native-combat-action-packets.json`. El
codec sólo cambia el segundo entero de esos headers. Preserva fightID, tercer
entero/specialID, todo el payload, UID/baseUID/stateUID y los cuerpos13420/13510.

`RuntimeMessages.prepare_delivery(packets)` asigna un contadorwire separado de
`RuntimeMessages.action_id` (request lógico). DevuelveNativeDelivery, que guarda
`native_actions` conopcode/request_action_id/native_action_id/special_id. Una
NativeDelivery ya preparada no se renumera al cruzar otra frontera del mismo
allocator. Contador inválido, header ajeno/truncado o agotamientosigned32
rechazan antes de publicación; no se reciclan IDs sobre acciones pendientes.

El commit común de hechizos/armas/Puño prepara la entrega después de completar
la serialización y validación, antes de adoptar el preview. Las fronteras
públicas deRuntimeMessages se preparan sólo en la invocación externa: inicio,
turnos, recovery, ACK y cleanup. Los paquetes pendientes del siguiente turno
permanecen sin numerar hasta recibir el13510 exacto. Esta preparación y el
avance de juego compartenpreview/adopt; fallar no avanza turno ni limpiaACK.

Las fronterasmain restantes (NPC, movimiento/áreas, muerte y resultados) deben
llamarprepare_delivery **a la lista final**. La entrega de commit/runtime ya
marcada puede pasar por el helper sin otra numeración. No renumerar por separado
cada fragmento de la misma lista. Los snapshots12873 mantienen su cola nativa;
no se añade ACK de efectos ni espera por tiempo.

Validación de esta entrega:8tests de IDs/ACK/agotamiento/rollback,6Runtime,
10Puño común y6checkpointPASS. Sin reinicio ni GUI en esta investigación. La
validación visual posterior debe usar un perfil exclusivo y comprobar HP final,
carrier real del manager y la correlación request→native_actions; no igualdad de
ID entre animación y daño.

## Comprobación de las fronteras finales y recursos gráficos

Después de integrar IDs,30regresiones en una ejecución cubren allocator, ACK,
RuntimeMessages, movimiento, muerte, resultados y lifecycle:PASS(0.999s).
La revisiónmain identificó además las listas de abandono12238 y orientación
13494: también necesitan la fronteraprepare_delivery. NPC, movimiento final,
muerte, resultados, commit y Ready deben preservar el marcadorNativeDelivery;
no deben asignar de nuevo IDs a cada fragmento de una entrega preparada.

`ProbeNativeSpellVisualDefinition` lee las definiciones originales bPS/bPK:
4777(Súper Puño)→script0;4776(Juicio)→1008130;4779(Ira)→1008140. Los tres tienen
cwF=false. aVm.cby selecciona bPK.cbH; aES no ejecuta un script conID0.
Los recursos1008130.lua/1008140.lua del JAR se identifican como Jugement4776 y
Colère De Iop4779. La ausencia de script propio4777 es compatible con esa
metadata instalada; no se inventa una animación ni se reutiliza la de otro
hechizo. No es evidencia de que la GUI haya mostrado correctamente las
animaciones o partículas de otras referencias.
