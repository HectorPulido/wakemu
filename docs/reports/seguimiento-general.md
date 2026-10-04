# Seguimiento general de Wakfu

Actualizado: 3 de octubre de 2026. Este es el índice global; el historial y el objetivo se conservan en [progress.txt](progress.txt).

El estado distingue lo confirmado jugando, lo probado internamente, lo integrado en archivos y lo pendiente. Un reporte antiguo de despliegue no demuestra que la última modificación esté cargada. Los resultados históricos no se suman como si fueran una única suite actual.

## Inventario exhaustivo de combate

[Abrir el inventario de combate](combat-inventory/README.md): 722 hechizos con nombres, 18 clases, 6.129 estados, 55.480 definiciones de efectos y relaciones entre condiciones, familias y estados. Incluye tablas descargables, prioridades, responsables, evidencias, límites y siguientes pruebas.

La última auditoría instala innatas en 18/18 clases al nivel 1 e innatas más seis pasivas en 18/18 al nivel 200. Es una prueba de instalación, no de funcionamiento durante el combate. No hay hechizos marcados como completamente comprobados jugando sin su evidencia individual.

## Solicitudes y sistemas

| ID | Solicitud o sistema | Estado acreditado | Pendiente o límite | Evidencia |
|---|---|---|---|---|
| G01 | Movimiento y giro | OK por ahora, confirmado por usuario | No reabrir sin fallo nuevo | [Reporte](estado-actual.txt) |
| G02 | Zaaps | OK por ahora, confirmado por usuario | No se probaron todos los trayectos | [Reporte](estado-actual.txt) |
| G03 | Dragopavos | OK por ahora, confirmado por usuario | No se probaron todos los trayectos | [Reporte](estado-actual.txt) |
| G04 | Inventario: mover, separar, agrupar, destruir, consumir | Pruebas internas y casos jugando; parcial | Ampliar a tipos y efectos especiales | [Reporte](estado-actual.txt) |
| G05 | Bolsas | Retirar/equipar/reconectar comprobado en cuenta aislada | Bolsas especializadas pendientes | [Reporte](estado-actual.txt) |
| G06 | Equipo y build visual | Parcial; errores reportados por usuario | Casilla vacía, duplicados visuales y conservación al reabrir deben probarse | [Reporte](combat-equipment-return-audit.md) |
| G07 | Bonos de equipo | Cálculo nativo e interno implementado | Confirmar 6→7→6 PA y ausencia de acumulación al reconectar y combatir | [Reporte](estadisticas-equipo.txt) |
| G08 | Puntos de características | Validación investigada/implementada según reporte | Confirmar guardar una asignación válida en cliente | [Reporte](aptitude-validation.md) |
| G09 | Equipo en Redis y lote de 20 minutos | Integrado en fuente | Carga y recuperación real posteriores a cambios deben acreditarse | [Reporte](scheduler-integration.txt) |
| G10 | Grupos de mobs en Redis y lote de 20 minutos | Integrado; pruebas con Redis real | No confundir fuente con versión cargada; límite de escritor único | [Reporte](grupos-redis.txt) |
| G11 | Posición y recuperación | Implementado y comprobado; Redis activo según historial | No repetir sin cambio de dependencia o fallo nuevo | [Reporte](estado-actual.txt) |
| G12 | IA separada del servidor | Servicio HTTP separado; implementación simple | No es IA completa de todas las especies | [Reporte](servicio-ia.txt) |
| G13 | Mobs moviéndose cerca de jugadores | Trabajo registrado en ecosistema | Verificar visualmente actividad, alcance y descanso sin jugadores | [Reporte](ecosistema.txt) |
| G14 | Semillas de monstruos y plantas | Plantación general integrada; modo abierto configurable | Ciclo completo jugando pendiente; cosecha de plantas no implementada | [Reporte](planting-runtime-local.md) |
| G15 | Extracción de semillas y materiales de monstruos | Handler y pruebas internas | XP de oficio y criterios complejos pendientes; comprobar cliente | [Reporte](recoleccion-monstruos.txt) |
| G16 | Reproducción de poblaciones | Pendiente de reglas completas | No sustituir reproducción por respawn artificial; comprobar población activa | [Reporte](ecosistema.txt) |
| G17 | Clima y retos de zona | Pendiente | Scheduler preparado no implementa estas reglas | [Reporte](scheduler-integration.txt) |
| G18 | Cron de guardados | Compose y callbacks integrados en fuente | Verificar versión cargada, ausencia de timers duplicados y lotes reales | [Reporte](scheduler-integration.txt) |
| G19 | Merkasaco básico y personalización propia | Persistencia parcial; fallo visual reportado | Confirmar sala básica sin gemas adicionales y salir sin desconectar | [Reporte](minimal-bag-nation-audit.md) |
| G20 | Pasaporte y datos heredados | Limpieza parcial; pasaporte reportado | Confirmar identidad/nación propias, sin datos de captura | [Reporte](minimal-bag-nation-audit.md) |
| G21 | Inventario de mapas y objetos interactivos | Catálogo y auditorías existentes | 934 mapas con geometría, 27 errores registrados; no implica todas las interacciones | [Reporte](map-inventory.csv) |
| G22 | Capturas y eventos entregados | Primera revisión de código realizada | 181 tipos; un tipo sin resolver y bloques anidados pendientes; no equivale a implementación | [Reporte](analisis-eventos.txt) |
| G23 | Consola chat y API de pruebas | Implementadas; chat confirmado por usuario | Usar API para pruebas; revisar límites de comandos concretos | [Reporte](local-test-console.md) |
| G24 | Launcher compartible sin cliente | ZIP mínimo y pruebas internas | GUI del ZIP independiente pendiente; Windows/Linux pendientes | [Reporte](mini-launcher-portable.txt) |
| G25 | Multiplataforma | Pendiente explícito | Validar Windows, macOS y Linux; no afirmar soporte por usar Python/Docker | [Reporte](estado-actual.txt) |
| G26 | Organización y limpieza de carpetas | Separación documentada | Preservar herramientas y pruebas útiles; consultar reporte antes de borrar | [Reporte](limpieza.txt) |
| G27 | Docker Compose y protocol por volumen | Configurados según historial | Protocol leído en memoria puede requerir recarga del proceso | [Reporte](docker-operacion.txt) |
| G28 | Enciclopedia, nombres de mobs y objetos | Catálogos y extracción documentados | Datos estáticos no son población, botín ni reglas ejecutables | [Reporte](enciclopedia-monstruos.txt) |
| G29 | Combates y colocación sobre terreno | Victorias confirmadas y múltiples casillas vistas | Altura, obstáculos, posiciones y todas las especies requieren pruebas | [Reporte](seleccion-arena.txt) |
| G30 | Entrada de varios jugadores al combate | Parcial/pendiente | Casillas disponibles no prueban compartir pelea entre conexiones | [Reporte](combat-multiplayer-join.md) |
| G31 | Rendición, muerte y salida del combate | Correcciones implementadas; errores previos registrados | Comprobar interfaz normal, movimiento y siguiente combate | [Reporte](combat-abandon-corrections.md) |
| G32 | Botín y experiencia al vencer | Sin validación completa acreditada en este inventario | Revisar fuente antes de marcar implementado; enciclopedia no basta | [Reporte](progress.txt) |
| G33 | Hechizos, pasivas y estados de las 18 clases | Objetivo activo; inventario detallado disponible | Ver subinventario; cero verificaciones individuales completas registradas | [Reporte](combat-inventory/README.md) |
| G34 | Osamodas e invocaciones | Pendiente de ciclo genérico de actores | Creación, propietario, control, turnos, muerte y catálogo | [Reporte](combat-inventory/README.md) |

[Tabla para filtrar en Excel](seguimiento-general.csv)

## Regla para no repetir trabajo

1. Buscar el sistema aquí y consultar su evidencia e historial antes de investigar.
2. Para combate, buscar también el hechizo, estado y familia en el subinventario; registrar revisión en `combat-inventory/review.json`, que el generador conserva.
3. Mantener responsable, fecha, versión/huella de fuentes, resultado, límites y siguiente caso concreto. Conservar fallos y pruebas anteriores.
4. Repetir una prueba cuando cambie el código o una dependencia, aparezca un fallo nuevo o falte un escenario; no repetir por perder el contexto.
5. Cerrar una tarea solo con evidencia de su alcance. Implementar un manejador no cierra todos los hechizos que lo usan.

## Pendientes de comprobación jugando

Equipo al reabrir/reconectar; semillas y recolección de ambos oficios; salida por rendición; incorporación de otro jugador; launcher distribuido; comportamiento de hechizos, pasivas y estados. El código nuevo de combate todavía requiere carga y comprobación en cliente.

No se realizó ningún reinicio para preparar este inventario.
