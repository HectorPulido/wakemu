# E05 — Selección activa: persistencia y publicación

## Alcance de esta revisión

Se coteja selección, metadatos y estadísticas. Decks/hechizos y sus pruebas quedan reservados a la otra sesión; el nombre histórico de la carpeta no autoriza intervenirlos. No se implementó ninguna corrección.

## Código y evidencia actuales

El esquema `characters` inspeccionado no tiene selección activa; `Store.character` carga hojas pero no incorpora `active_build_index`. `build_set` serializa siempre `proto_field(8,0)` como selección activa. En cambio, `equipment_stats.bonuses` y `aptitudes.bonuses` ya leen `character.get("active_build_index",0)`: no están rígidamente fijados a0 si el modelo trae otra selección. La brecha principal es autoridad/hidratación y publicación, no ausencia total de soporte del campo en esos consumidores.

[Probe actual](probe-seleccion-estadisticas-actual.json): modelo sintético nivel100 con build2/10 puntos HP y `active_build_index=2`; estadísticas dan **1470 HP máximos**, pero `build_set` anuncia **0**. Al omitir selección, estadísticas usan fallback0 y dan **1050**. Se comprobó también ausencia de columna de selección en esquema desechable. No hubo decks, turnos, hechizos ni GUI.

La activación nativa13776 y ACK13811 se cotejaron en issue34; no se encontró handler13776 en el dispatcher actual. Guardar12772/12284 no constituye activación. La selección de fila editada en el cliente tampoco determina qué build gobierna al personaje.

## Solución concreta del servidor

Persistir selección activa y revisión como estado del personaje, referenciada a un índice existente. Hidratarla junto con las hojas autoritativas SQL/journal; si la selección apunta a una hoja ausente, diagnosticar y resolver fallback validado, no ocultarlo silenciosamente con cero. Publicar el índice efectivo en `build_set` y usarlo para equipo, aptitudes y estadísticas del mismo snapshot.

Implementar transición de activación propia con ownership/lease, existencia, fase permitida y actualización de salud coherente (E12). Congelar selección/revisión en el snapshot del combate para que editar una secundaria no cambie el combate en curso. Dejar guardado y selección de edición independientes de activar.

En eliminación activa, confirmar fallback antes del ACK12837 según consumidor nativoE07; incluir selección y tombstone en una transición durable. Redis/SQL no deben confirmar mitades independientes (E06). Coordinar con la sesión responsable de decks mediante contrato de selección/revisión, sin introducir aquí cambios de hechizos.

## Pendientes de reproducción

Activación y reconexión autenticadas de secundaria; rollback/retry y borrado activo; snapshot efectivo coherente con GUI. El modelo sintético prueba capacidad de estadísticas e incoherencia de publicación, no que build2 pueda activarse hoy desde cliente. La auditoría sigue abierta.
