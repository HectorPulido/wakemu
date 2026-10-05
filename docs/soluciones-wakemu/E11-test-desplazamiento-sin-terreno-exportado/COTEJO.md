# Cotejo de código — E11

- [server/tests/test_combat_spell_transaction.py](../../../server/tests/test_combat_spell_transaction.py), SHA-256 `89fa1b368f1a39d2124fdacd1225f8cf88f18fc7b2238bdde204522c949a0877`.
- [server/wakfu_server/combat/combat_forced_terrain.py](../../../server/wakfu_server/combat/combat_forced_terrain.py), SHA-256 `8cc405faa2e6de53380791cc6e41685e1143f9e1a6d55df241df11fdb4c6b6ef`.
- [server/wakfu_server/combat/combat_displacement.py](../../../server/wakfu_server/combat/combat_displacement.py), SHA-256 `35f333aa7df4dbe5b77ea07e373a7395d305d0619b3bbae9cc0a85166b06abe2`.
- [server/wakfu_server/combat/combat_server_spell.py](../../../server/wakfu_server/combat/combat_server_spell.py), SHA-256 `4fa98a464001bdf7ef399e8ddf0406abc5fdbe12c0810d6d8e24dabcd398278b`.

## Contratos contrastados

- test_combat_spell_transaction.native_server_fixture mezcla geometría sintética y NPC con map_id=1134.
- combat_displacement.__call__ usa metadata.native_instance_id para decidir consultar la política nativa; usa altura, radio físico y jump=4.
- combat_forced_terrain.next_surface busca exactamente (source, xy); si no existe, lanza el ValueError observado. None tiene significado diferente: una colisión exportada.
- prepare_spell_transaction opera sobre preview y no envía antes del éxito; el rechazo del efecto debe preservar recursos y estado originales.

No sustituir el error por None ni por geometría de caminar para hacer pasar el test: eso ocultaría una consulta desconocida. Las políticas de movimiento forzado y caminar son distintas.

## Reproducción dirigida y causa acotada

Se repitió el test con instrumentación en memoria: mapa 1134, altura 4, radio 0, jump 4, origen `(2,0,0)` y destino XY `(3,0)`. La consulta y el origen no existen en la exportación de movimiento forzado. Además, ni `(2,0,0)` ni `(3,0,0)` pertenecen a las celdas transitables reales exportadas del mapa 1134.

Esto confirma la incoherencia de la fixture: combina coordenadas de un plano sintético con autoridad de un mapa real. El rechazo no demuestra una carencia del catálogo para posiciones reales. La solución propuesta debe corregir esa coherencia en los tests y conservar el rechazo por consulta desconocida; no relajar el runtime. [Resultado estructurado](probe-consulta.json).
