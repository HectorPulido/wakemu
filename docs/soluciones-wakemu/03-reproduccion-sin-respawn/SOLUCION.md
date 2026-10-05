# Solución propuesta — 3

Crear descendencia y ampliar grupos por reproducción o siembra, sin respawn automático independiente.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Inventariar vías actuales de creación

Listar bootstrap de grupos, crecimiento de semillas, retorno tras combate y respawn. El requisito del usuario elimina respawn automático salvo reproducción/siembra. Distinguir liberar un grupo no derrotado de regenerar uno muerto; cambiar solo population.enabled no crea un servicio ni desactiva esas rutas.

## 2. Aplicar las reglas de reproducción solicitadas

Usar familia y escalón de nivel; ignorar sexo. Máximo 8 miembros por grupo. En cada intervalo configurable evaluar por separado crecimiento del miembro y nacimiento de otro; la probabilidad depende del nivel actual y del siguiente, con 5% como ejemplo configurable, no constante oficial. Reservar una celda válida antes de crear la cría. Si el grupo está lleno, evaluar un nuevo grupo únicamente con capacidad y posición válidas. No recuperar NPC muertos por temporizador.

## 3. Persistir población y eventos de nacimiento

Registrar por zona/instancia grupo, miembros, padres, última reproducción y birth_event_id único. Mantener contador derivable de miembros vivos; reservar celdas legales y cupos por familia/zona antes de generar identidad. El recibo impide duplicar crías por cron/retry.

## 4. Evaluar solo zonas con jugadores

Integrar con el scheduler de 20 y sus relojes pausables. No procesar zonas vacías ni recuperar todos los nacimientos ausentes al entrar. Seleccionar candidatos próximos mediante índices, evitando comparaciones cuadráticas entre toda la población.

## 5. Confirmar y publicar nacimiento

Bajo revisión/cupo, crear un miembro o grupo y actualizar padres/cooldown en un commit durable. Si el destino entra en combate durante cálculo, replanificar. Emitir snapshot/delta nativo del nuevo grupo a todos los jugadores relevantes después del commit.

## 6. Desactivar regeneración incompatible

Eliminar de la futura política cualquier recuperación automática de NPC derrotado que no tenga birth_event o siembra confirmada. Conservar reservas, cadáveres/recolección y cleanup. Sembrar sigue consumiendo semilla una sola vez; no usar reproducción para ocultar reposición ilimitada.

## 7. Controlar capacidad y recuperación

Imponer máximo por grupo, familia y zona; saturación pospone o cancela el nacimiento según regla. Reabrir journal con recibos sin generar hijos de nuevo. Guardar métricas births_applied/births_deferred, ocupación y tiempo de tick.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Cada nueva unidad tiene origen durable de siembra o reproducción; matar y esperar no genera unidades.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
