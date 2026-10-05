# Issue 20 — Población inicial y suspensión de zonas

## Requisito

Pocos monstruos iniciales por zona, multiplicación posterior y ninguna actividad de movimiento o reproducción mientras no haya jugadores. Reglas y tiempos deben parametrizarse en DB. No se implementó ningún cambio.

## Código actual cotejado

El arranque registra un único grupo de pruebas en mapa **1134**, instancia **0**, ID **200**, con una o dos criaturas de referencia **5525**, nivel 1, IDs −200/−201 y posiciones (−7, −7, −1)/(−7, −6, −1). `register_seed` intenta preservar estado previo; no es un catálogo de población inicial por zona. La capacidad de este grupo solo acepta 1 o 2, independientemente de las plazas de colocación del combate.

`wander_monsters` enumera mapas/instancias presentes en `WORLD.snapshot`; `wander_location` devuelve inmediatamente si no hay jugadores de esa localización. Además exige proximidad de 20 celdas. El worker global espera aleatoriamente 3–6 segundos; cada grupo elegible intenta un paso. No aplica todavía el requisito de 5 segundos, 25% de oportunidad y cantidad aleatoria de pasos.

La suspensión es incompleta: `grow_planted_resources` llama a `PLANTINGS.mature` sobre todas las plantaciones vencidas. Su callback `free_spawn` comprueba ocupación, no presencia de jugadores. `mature` usa tiempo de reloj desde creación y puede crear monstruos después de salir todos. `respawn_monsters` tampoco filtra zonas activas antes de `respawn_due`; repoblación de grupos derrotados no equivale a reproducción ecológica. No se encontró en estas rutas un ciclo de reproducción de adultos con nuevas crías.

## Reproducción aislada

[Probe y hashes](probe-zona-sin-jugadores.json): en SQLite desechable, semilla 30927, completar plantación y avanzar 30 segundos creó **un grupo** y mensajes **12782/12608**, sin suministrar presencia alguna. La plantación desapareció al transformarse. El servicio no recibe una lista de zonas activas que pueda impedirlo. Separadamente, `wander_location` sin jugadores retornó vacío sin siquiera acceder al registro de grupos. Confirma la diferencia entre suspensión de movimiento y crecimiento; no acredita un scheduler real ni reproducción de adultos.

## Solución concreta del servidor

Crear catálogo DB de población inicial por región ecológica y mapa/instancia, con referencias, nivel, cantidad mínima, máximo y puntos válidos derivados de topología. Usar una marca durable de inicialización por zona y versión: reingresar o reiniciar no debe volver a sembrar todos los grupos. No confundir instancia de merkasaco/mazmorra con mundo abierto ni poblarla usando reglas globales.

Mantener presencia con leases de sesión y contador/revisión de zona. Una desconexión expira la presencia; teletransporte debe quitar origen y añadir destino. Precisar región ecológica dentro del mapa, pues el filtro actual solo reconoce mapa/instancia. Derivar tareas activas de presencia autorizada, sin escanear toda la geometría por cada grupo.

Persistir tiempo activo acumulado y restantes para envejecimiento/reproducción; al desactivar una zona congelar sus tareas, y al reactivar no simular reproducción por todo el tiempo de ausencia. Separar esta política de crecimiento vegetal cuando corresponda y registrar explícitamente su ámbito. El instante real de creación actual no basta para medir tiempo activo.

Reservar población, identidad de cría y celda bajo una operación atómica con recibo durable; validar padres disponibles, cupos, especie, terreno y ocupación. Usar outbox para publicar nuevos grupos sin duplicar tras caída. Padres en combate o cosecha no participan. Cambiar presencia durante un cálculo requiere cotejo de revisión antes de confirmar.

Pruebas pendientes: dos jugadores entrando simultáneamente, salida del último, reconexión, caída de proceso, dos workers, límite poblacional, padres en combate y recuperación de outbox. La ausencia de un consumidor conectado no debe confundirse con ausencia de cambios persistentes. Este issue continúa abierto para reproducción gráfica y diseño de datos por región.
