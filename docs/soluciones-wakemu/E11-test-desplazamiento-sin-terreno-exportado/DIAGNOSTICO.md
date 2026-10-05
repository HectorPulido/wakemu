# Diagnóstico — E11

El lote dirigido de revisión ejecutó 33 tests en 18,714 segundos: 32 correctos y 1 error. Falló test_server_entry_conditional_spell_damage_and_displacement_share_transaction con ValueError: Native forced terrain source/query is not exported. No se aplicó ninguna corrección.

La fixture native_server_fixture construye un plano sintético, con caster en (0,0,0) y target en (2,0,0), pero el NPC lleva identidad nativa del mapa 1134. El desplazamiento invoca next_surface con esa identidad y coordenadas del plano. next_surface diferencia una colisión exportada (None) de una consulta ausente (error).

Se confirma que la prueba no alcanza sus assertions finales. No se ha probado que las coordenadas pertenezcan al mapa exportado ni que el movimiento falle con una colocación válida real. El error puede deberse a fixture incoherente, cobertura incompleta o metadata equivocada; requiere el cotejo siguiente.

## Reproducción dirigida y causa acotada

Se repitió el test con instrumentación en memoria: mapa 1134, altura 4, radio 0, jump 4, origen `(2,0,0)` y destino XY `(3,0)`. La consulta y el origen no existen en la exportación de movimiento forzado. Además, ni `(2,0,0)` ni `(3,0,0)` pertenecen a las celdas transitables reales exportadas del mapa 1134.

Esto confirma la incoherencia de la fixture: combina coordenadas de un plano sintético con autoridad de un mapa real. El rechazo no demuestra una carencia del catálogo para posiciones reales. La solución propuesta debe corregir esa coherencia en los tests y conservar el rechazo por consulta desconocida; no relajar el runtime. [Resultado estructurado](probe-consulta.json).
