# Plan de implementación y criterios de entrega

El motor nuevo y el puente inicial están implementados; la aceptación completa de las etapas sigue en curso. Cada etapa tiene resultado revisable y puerta de aceptación; ordenado para no duplicar el motor de hechizos de la otra sesión.

| Etapa | Cambios concretos | Salida y aceptación |
|---|---|---|
| A. Contrato NPC | Autoridad de habilidad/nivel, target, recursos y usage; generalizar ruta hoy limitada a Wonejo | Dos referencias con repertorios distintos lanzan solo habilidades propias; legalidad, recursos, rollback y paquetes cotejados |
| B. Adaptador/semántica | DTO, tags multirol, unknowns, acciones tipadas, preview aislado | Tabla por habilidad/efecto y candidato reproducible; forecast no consume RNG/UID ni escribe el estado real |
| C. Decisión de una acción | Ranking determinista de ataques/heal/buff/end; legalidad centralizada | Elige objetivo útil por consecuencias y respeta costes/rango/estados; ya no ataque hardcoded universal |
| D. Secuencias | Refactor búsqueda Dofus con adapter, beam, poda, límites y ACK/replanning | Cast repetido legal, movimiento para tiro y retirada; cero-cost sin loops; invalidación de plan tras reacción |
| E. Espalda y alturas | native_facing, dirección final, rays/huellas XYZ, amenaza rival | Corpus ocho direcciones, límites geométricos, escalera, alturas superpuestas, ruta peligrosa y exposición propia |
| F. Equipo | Foco, curación útil, reservas/corredores, memoria con UUID/revisión | Dos melee+ranged+support actúan sin bloquearse; muerte del foco y cambio de turno invalidan memoria |
| G. Perfiles y operación | DB de policy, límites/concurrencia, traces, timeouts, corpus y replays | Mismos snapshots/policy producen resultado reproducible; carga concurrente y fallback sin trabar combate |
| H. Mecánicas especiales | Invocaciones, zonas y bosses según soporte del motor | Cada referencia soportada con prueba propia; desconocidas identificadas y sin consecuencias inventadas |

## Cambios por archivo y responsabilidades

**Reutilizar/refactorizar desde Dofus:** búsqueda y diversidad de `tactical_planner`; generación de intenciones de `intent_ai`; coordinación y cache de `team_memory/turn_strategy`. Crear variante independiente en Wakemu con dependencias inyectadas. No mantener imports a `/Users/hectorpulido/dofus`; un clon limpio debe funcionar sin ese checkout.

**Servicio Wakemu:** `server/ai-service/planner.py` deja de ser exclusivamente BFS y orquesta capas propuestas `semantics`, `intents`, `search`, `scoring`, `team_memory`. `server.py` valida protocolo 2, límites de tamaño/tiempo/concurrencia y errores. BFS actual se conserva como algoritmo de rutas/fallback donde sea legal, no como única política de combate.

**World:** `combat_ai.py` amplía snapshot/validación y deja de imponer attack=null. `combat_movement_runtime` integra ruta/orientación/reacciones. Crear transición NPC común junto a `combat_server_spell`, reutilizando handlers y commit; coordinación con el otro agente antes de editar módulos compartidos. `pass_test_monster_turn` pasa a ciclo acotado decisión→acción→ACK→redecisión→fin, evitando ejecutar movimiento y ataque detrás de sincronización pendiente.

**Catálogos:** exportación determinista con manifest/version de habilidades, costes/usage, árboles de efectos, geometría y perfiles. No copiar assets de cliente completos ni dependencia de paths privados. Efectos soportados cambian durante trabajo de la otra sesión: guardar fingerprint por resultado, no considerar permanente el conteo de handlers.

## Validación que evita resultados engañosos

1. Unitarias de adapters: celda/altura/orientación, recursos y tags; no duplicar reglas del motor en tests tautológicos.
2. Differential/replay: la acción elegida se ejecuta en copia nueva del snapshot; deltas coinciden con preview y no aparece consumo previo. Comparar con la IA actual como baseline de mejora, sin afirmar fidelidad oficial por ganar.
3. Integración world/HTTP: respuesta obsoleta, timeout, fallo después de commit, repetición, aislamiento entre encuentros, ACK y end-turn.
4. Juego con personajes de prueba: GUI/observadores, estados, orientación, costes y desplazamiento; delegar UI a Luna low o usuario. Test interno no reemplaza estos recorridos.
5. Rendimiento: corpus pequeño/mediano/complejo y varios combates simultáneos; tiempos p50/p95/p99, CPU, RAM, nodos, bytes, cache hit y timeouts. Elegir presupuestos después de medir, no importar 180ms como garantía.

## Alcance inicial recomendado

Primera entrega útil: enemigos con daño/curación/armadura ya ejecutables, movimientos reales, selección de blanco, buscar espalda y retirada básica. A continuación coordinación multienemigo y altura compleja. No esperar a que las 3091 habilidades estén completas para mejorar IA; tampoco declarar que todas funcionan por pasar el inventario.

Dificultad se ajusta con profundidad, pesos, tolerancia al riesgo y coordinación; evitar aumentar daño/recursos ocultamente bajo una etiqueta de IA. Mecánicas de mazmorra mantienen sus multiplicadores en su propia configuración, coordinada pero separada.
