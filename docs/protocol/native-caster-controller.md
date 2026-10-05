Consulta del controlador para el mazo

El selector casterController de eII.a resuelve primero el lanzador, obtiene el fbX del contexto y busca fbX.rj(eHg.dTD()). eGj.dTD usa dpr().aHm; no usa dueño de cuenta, equipo ni dpu directamente. Para jugadores big.dpr llama dnH, que usa eGj.c(controller,this). Con controlador de creación nulo ese helper devuelve el propio jugador; si el grupo no encuentra sustituto también conserva al jugador.

NativeActorAuthority ahora expone native_controller_id como identidad explícita opcional. La autoridad de creación ordinaria sólo acredita el propio jugador en ausencia de relaciones nuevas; NPC e invocaciones permanecen desconocidos hasta acreditar su dpr. El adaptador lee el mazo del actor controlador actual en el roster, sin copiar el mazo del lanzador. Datos desconocidos conservan rechazo explícito.

Regresión de adaptador: lanzador NPC sin mazo, controlador jugador con mazo, búsqueda correcta; sin metadata de controlador la consulta falla y no inventa un mazo vacío. Bytecode: native-actor-selector-current.txt, native-controller-actor-current.txt y big.txt en .runtime/local. No implica comprobación en cliente ni soporte completo de todas las relaciones de control.
