# Solución específica del servidor

Propuesta, sin implementación. Conservar la interfaz nativa y portar un motor de logros/misiones con contratos explícitos, en lugar de llenar el diario de entradas completadas.

## Catálogo e interpretación de criterios

Exportar los tipos 1/2/3/115 mediante los lectores actuales a un catálogo versionado del servidor. Conservar IDs, categoría/padre, objetivos/listeners, recompensas/params, flags, niveles recomendados, duración, cooldown, periodos, orden y referencias. Crear un manifiesto con hashes, duplicados, referencias ausentes y campos todavía opacos. Los textos sirven para revisión; el runtime usa IDs, no traducciones.

Separar logros de misiones por la organización/metadatos que usa el consumidor nativo. No inferir la clasificación solo de `isVisible`, ni activar automáticamente todas las entradas. Exportar las expresiones completas: existen `and`, `or`, `not`, comparaciones y funciones como `IsAchievementComplete`, `IsAchievementObjectiveComplete`, `GetAchievementVariable`, `GetRealLevel`, `GetDate`, `GetInstanceId`, `IsInGuild` y configuración. Usar parser restringido a una gramática y funciones autorizadas, **sin eval**. Una función desconocida deja esa regla sin soporte identificado; no devolver true.

El loader `aZx` añade condiciones para contratos mercenarios: nivel, objeto de acceso y logros de rango previo. Guardar expresión original y normalización equivalente; importar únicamente `cjI` omitiría esas condiciones derivadas. Cooldowns y reglas configurables viven en DB, según el requisito transversal.

## Estado y eventos autoritativos

Tablas propuestas en PostgreSQL, añadidas mediante migración E01:

| Tabla | Clave / datos imprescindibles |
| --- | --- |
| `achievement_definitions` | version,id; categoría, metadatos y criterios normalizados |
| `achievement_objective_definitions` | version,objetivoId; logro padre, listeners y regla/productor verificado |
| `achievement_reward_definitions` | version,rewardId; logro padre,tipo,params |
| `achievement_state` | personaje,logro,ciclo; activo/completo, fechas, expiración, versión catálogo, revisión |
| `achievement_variable_state` | personaje,variable,ámbito/ciclo; valor bigint, revisión |
| `achievement_objective_state` | personaje,objetivo,ciclo; progreso/completo, revisión |
| `achievement_tracking` | personaje,logro; orden/seguimiento |
| `achievement_event_receipts` | eventUUID,personaje,regla,ciclo; restricción única de procesamiento |
| `achievement_reward_receipts` | personaje,logro,ciclo,rewardId; grant durable/idempotente |
| `achievement_outbox` | personaje,revisión,eventUUID; notificaciones pendientes tras commit |

El actor del protocolo no demuestra que el alcance de cada regla sea cuenta: mantener por personaje como implementación inicial y registrar explícitamente excepciones acreditadas, sin compartir premios entre personajes por accidente. Variables con ámbito global/cuenta necesitan su contrato propio antes de activarse.

Producir eventos **después de acciones aceptadas**: victoria/finalización de combate con UUID y participantes; misión/interacción validada; exploración con región/mapa/instancia; fabricación/plantación confirmada; pertenencia a gremio; avance de mazmorra con sala/dificultad; transición de nivel. Cada regla filtra tipo, objetivo, ámbito, elegibilidad y ciclo. Fallos, simulaciones, paquetes repetidos, combates abandonados y muertes fuera de una victoria no equivalen automáticamente a avance.

Indexar variable/evento→listeners→objetivos→logros/metalogros. Recalcular solo afectados; cola hasta punto fijo con deduplicación y detección de ciclos. Conservar objetivos independientes y no completar todos ante la primera variable modificada. Al terminar un hijo, actualizar sus padres una sola vez, incluso tras recuperación.

## Caso 4228 y entrenamiento 3976

Resolver IDs hijos de 8716/8717/8718/8723/8724/8725 mediante catálogo completo y fuentes de escenarios. Cada finalización durable del hijo activa solo el objetivo correspondiente; 8723 se vincula a 177 y 8724 a 3976, acreditados por nombre/ID nativo. El enlace textual requiere formalización revisada, no un match en tiempo de juego. Cuando los seis estén completos, finalizar 4228 y entregar una 16942 con recibo 7936 único en la misma transacción.

Para 8539, localizar el encuentro de Tristepin y su marcador de finalización: `scenario/2258.lua` solo presenta inicialización vacía y no acredita el encuentro por su número. Registrar cinco eventos elegibles diferentes, persistir progreso 1→5, completar 3976, título 520 y diez 14168. No contar cinco aperturas de diálogo ni cinco retransmisiones de una misma victoria. Si falta el evento de entrenamiento, reportar esa regla sin soporte, manteniendo las demás implementables.

## Recompensas, repetición y recuperación

El enum nativo contiene 19 tipos, pero el catálogo usa 12. Predominan tipo 5 objetos (2.796 entradas),6 XP (1.405),17 XP por XP de mob (574),11 kamas (380),2 títulos (349). También hay registro de zaap/drago, emotes, landmark, receta, puntos de gremio y hechizos. Son **conteos de definiciones**, no cantidades entregables.

Implementar handlers por tipo y validar aridad/semántica de params con sus consumidores. Reutilizar servicios de inventario/UID, XP, kamas, títulos y transportes, conservando sus permisos y límites. Tipo 17 no equivale a XP fija: resolver base/nivel/fórmula antes de concederlo. Tipo 16 concede un hechizo: queda coordinado con la otra sesión; no modificar su motor durante esta auditoría. No marcar el premio entregado cuando falta su handler.

Finalización+recibos+grants+outbox se confirman de forma atómica. Si el inventario está lleno, usar una entrega pendiente durable si se valida su protocolo; no borrar el premio ni emitir éxito ficticio. Reconectar solo restaura estado: jamás vuelve a conceder premios. Las recompensas repetibles usan una identidad de ciclo explícita; completar un periodo no habilita infinitos grants.

Tiempos calculados con reloj del servidor; probar expiración, enfriamiento, reinicio y frontera de periodo. Las fechas de catálogo y el control local de 30 s no reemplazan esos cálculos. No resetear todos los logros al cambiar día ni usar ciclos según hora del cliente.

Redis puede acelerar snapshots y journals, pero ningún premio debe depender de un snapshot antiguo mientras hay mutaciones pendientes. Si se difiere SQL20 min, el avance y recibo necesitan journal durable con revisión/recuperación antes del ACK; no mezclar premio SQL inmediato y progreso Redis no durable. E01 y el contrato transversal definen la estrategia.

## Entregables por etapas

1. **Catálogo**: nuevo `server/tools/export_achievements` y `server/protocol/achievement-catalog`; validación completa de referencias y matriz por objetivo: productor acreditado / regla explícita / sin soporte. No introducir blobs del cliente en commits.
2. **Motor/almacenamiento**: módulos propuestos `wakfu_server/achievements/{catalog,criteria,events,service}` y almacenamiento; migración, estados, deduplicación, padres y ciclos con fixtures pequeñas.
3. **Wire/dispatcher**: encoder versión 5, bootstrap real, incrementales y solicitudes nativas; tests contra consumidores Java, pertenencia a sesión y orden de publicación.
4. **Primer flujo real**: logro con contador acreditado + uno de exploración + cadena Astrub→4228, recompensas y reconexión. Usar personaje nuevo, no completar entradas en la DB para simular éxito.
5. **Integración**: oficios/ecosistema, grupos, mazmorras, gremios, periódicos; cada familia se cierra con eventos reales y pruebas de reinicio. No esperar a que existan todas las mazmorras para implementar el núcleo.

Métricas: eventos procesados/duplicados, reglas sin soporte, latencia p 95/p 99 de avance, tiempo de bootstrap, tamaño blob, grants fallidos y outbox pendiente. Evitar recorrer 6.029 objetivos y consultar SQL por cada movimiento del mundo.
