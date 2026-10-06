# Pruebas y aceptación — E10

## Revalidación PostgreSQL — 2026-10-05

El lote de aptitudes/builds/equipo indicado en E08 ejecutó **54 tests OK** con PostgreSQL aislado y migraciones 001–008. Incluyó `test_builds`, `test_build_capacity`, `test_equipment_stats`, `test_equipment_full_set`, `test_equipment_full_set_ready`, `test_equipment_combat_integration` y `test_ring_build_integration`.

| Invariante | Evidencia actual |
| --- | --- |
| Guardar y reabrir build | `test_save_response_and_reopen_are_authoritative`: blobs guardados reaparecen idénticos tras cargar Store nuevo. |
| Build nueva entra al registro publicado | `test_save_response_publishes_new_owned_registry_entries`: carrier12393 contiene índices0 y127; respuesta emite ACK12284, registro12393, aptitudes12103 y snapshot13046 en ese orden. |
| Catálogo uniforme | `test_metadata_equipment_and_aptitudes_share_catalog` produce los mismos índices para metadata, equipos y aptitudes. |
| Publicación tras edición de anillo | `test_ring_build_integration` verifica reabrir y emitir registro al guardar la hoja modificada. |

La función histórica `equipment_set` ya no tiene caller y fue retirada; la cobertura valida el constructor y las respuestas actualmente conectadas al flujo. Los paquetes generados se han cotejado además con el consumidor Java del carrier12393. No se ejercitó el dispatcher socket completo ni una sesión gráfica del cliente: la visualización de la fila y todas las transiciones de guardar/activar/borrar siguen pendientes de aceptación nativa.


## Aceptación visual — 6 de octubre

El usuario confirmó los seis pasos completos con Audiluna y la build Prueba E10: creación/activación, equipo visible y guardado, alternancia independiente, cambio de personaje, reinicio del cliente y borrado persistente sin pérdida ni duplicación de objetos. Este recorrido completa la verificación visual antes pendiente.
