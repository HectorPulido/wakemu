# Cotejo de IA existente y referencia Dofus

## Wakemu hoy

- `server/ai-service/wakfu_ai/planning/planner.py::decide`: BFS sobre aristas dirigidas 3D, respeta ocupación y presupuesto PM; busca adyacencia a un enemigo. Devuelve `attack=None`. No considera hechizos, resistencias, curación, orientación, exposición ni equipo.
- `combat/combat_ai.py::snapshot`: protocolo 1, requestId/stateKey, turno, geometría, actores con equipo/HP/PA/PM/control. Faltan HP máximo, PW, dirección, estados, hechizos y amenazas. Su hash protege solo los datos incluidos. `validate` rechaza cualquier ataque no nulo; HTTP timeout 1 segundo y fallback sin movimiento.
- `combat_movement_runtime.apply_ai`: ejecuta recorrido validado; existe integración opcional de eventos de área. No basta el pathfinder para modelar costes/reacciones especiales de movimiento. El caller actual usa dirección 3.
- `local_game_server.py::pass_test_monster_turn`: acercarse, intentar un ataque, terminar turno. La política de ataque no viene del servicio.
- `combat_npc_attack.ability/execute`: whitelist ref 5525, habilidad 7962, una vez por turno como política local; objetivo jugador concreto. Parte del daño ya pasa por el dispatcher común, pero esto no es un lanzador genérico de todas las habilidades NPC.

Catálogo disponible: **2874 monstruos**, 1934 con habilidades; **3091 IDs distintos de habilidades**, todos presentes en las **4143 tablas nativas de lanzamiento**. Propiedad y nivel salen de `maps/monsters.native_abilities`, campo csd/aMk; **csr corresponde a loot y no debe usarse como lista de hechizos**. `combat_native_spell_casting.definition` aporta costes, alcance, LOS, linealidad, celda libre, condiciones y raíces. La presencia de tabla no acredita todos los niveles, condiciones, efectos ni mecánicas.

Se ejecutaron 18 tests de IA actual/cliente HTTP/servicio, todos pasan. Tres fixtures muestran que añadir rol ranged/support y metadata de hechizos a la petición no altera el resultado actual: los tres acercan hasta melee y no proponen atacar. No es prueba del nuevo motor.

## Qué reutilizar de Dofus, concretamente

| Archivo de referencia | Sistema aprovechable | Adaptación Wakfu |
|---|---|---|
| `spell_catalog.py` | Clasificación semántica de efectos y capacidades | Registro por familias/runners de Wakfu; no copiar IDs de efectos Dofus |
| `intent_ai.py` | Rematar, desgastar, curar/proteger, invocar, acercarse, trabar, retirada/kiting; prioridad de blancos | Fuente de intenciones/estructura; reemplazar geometría, daño, resistencias, recursos y reglas de legalidad |
| `planner.py` | Generación, poda, evaluación de estado, secuencias y búsqueda acotada | Conservar estructura; sustituir Board/celdas y simulador de reglas Dofus por adaptador de combate Wakfu |
| `tactical_planner.py` | Alternativas de turno, límite de nodos/tiempo y diversidad de objetivos | Secuencias mover→lanzar→retirarse y presupuesto medido; parámetros 180 ms/576 nodos son defaults Dofus, no objetivos de rendimiento acreditados para Wakfu |
| `team_memory.py` | Roles por capacidades, foco, reservas de posiciones, protección de soportes, historial anti-oscilación | IDs y XYZ nativos; memoria por encuentro estable/instancia/equipo; confirmar solo acciones ejecutadas |
| `turn_strategy.py` | Mantener intención/objetivo entre decisiones del mismo turno | Cachear intención, nunca un plan ejecutable desactualizado; selección determinista sin llamada neuronal |
| `engine.py` | Orquestación, perfiles, clasificación y ranking | Pipeline sin Laya; TinyPolicy opcional futuro, sus pesos/features no son intercambiables |
| fixtures/tests/simuladores | Casos de regresión y evaluación táctica | Reescribir fixtures con Wakfu; no ejecutar el proyecto Dofus localmente |

No trasladar Laya, sus imports, autenticación, prompts ni selección remota. `decision_trace.py` está centrado en telemetría Laya; reutilizar la idea de traza, no sus métricas como diagnóstico táctico.

## Límites que no conviene heredar

El simulador Dofus aproxima efectos y conserva opacos. En Wakfu, una rama obligatoria no soportada no puede puntuarse como si tuviera un efecto conocido ni omitirse durante la ejecución. La clave de memoria Dofus usa fightId, roster y hashes de geometría; reemplazarla por UUID del encuentro, instance/map/team y revisión estable. `TeamCoordinator.commit` se llama tras seleccionar plan en el engine: Wakfu debe actualizar reservas/foco tras resultado confirmado por world, no por una intención todavía no ejecutada.
