# E10 — revisión del flujo vigente

`equipment_set` sigue declarado, pero la búsqueda de callers en todo `server/` solo encuentra su definición. El diagnóstico de reemplazo sin inserción se refiere a una función actualmente fuera del flujo.

El registro vigente es `builds.equipment_registry`, que sí enumera todos los índices guardados y se usa mediante el carrier nativo12393. Su conjunto incluye0, mientras `build_set` y `aptitude_registry` también publican1. Esta discrepancia y la actualización después de guardar una hoja nueva deben verificarse en los consumidores nativos y en el dispatcher.

No se considera resuelto E10 por esta lectura ni se altera una función sin callers como supuesto arreglo de comportamiento real. Próximo cambio: unificar catálogo y asegurar publicación del registro al crear/activar/borrar y al reconectar.

## Catálogo común implementado

Metadata, registro de equipo y aptitudes usan ahora `catalog_indices`:0,1 y todos los índices guardados válidos. Se incluye equipo vacío nativo para Build1, antes ausente del registro. Se eliminó `equipment_set`, sin callers, para evitar conservar otro camino de actualización incompatible.

Suite:42 casos, **32 PASS y10 SKIP**. Una regresión compara las tres colecciones con una hoja127 y verifica conjuntos idénticos. Las pruebas de bootstrap y anillo ahora preservan todas las entradas protobuf repetidas; convertir ese campo a dict descartaba registros y ya no es una verificación válida con varias hojas.

Pendiente: publicación del registro después de guardar/activar/borrar y validación nativa/visual de esas transiciones. No desplegado todavía; E10 continúa parcial.

## Publicación después de guardar

La respuesta de guardado exitoso emite ACK12284, registro de equipo12393, aptitudes12103 y snapshot de estadísticas13046. Registro y aptitudes incluyen todas las hojas del catálogo común.

Bytecode nativo: `cia` decodifica12393 con `fpi.eO` y registra cada personaje con `fpo.a`; este sustituye únicamente la clave cuenta/personaje mediante `Table.put` y notifica listeners. Una actualización del personaje propio no elimina registros de otros personajes.

Suite:43 casos, **33 PASS y10 SKIP**. Regresión verifica orden, longitudes, actor y nueva entrada127. Los intentos iniciales del nuevo test fallaron por campos ausentes en su fixture; se completó identidad y posición antes del PASS.

Pendientes: activación/borrado y aceptación visual; actualización aún no desplegada.

## Ejecución del consumidor nativo

El probe Java ejecutó `cxD.dp`, `fpi.eO` y `fpo.a/aN` sobre los bytes generados por el servidor: **PASS native12393 indices=0,1,127 other-character-preserved**. La hoja127 queda accesible mediante `Wk(127)` y el registro de otro personaje permanece presente. Herramienta/payload privados en `.runtime/local/VerifyBuildRegistry.java` y `e10-registry.bin`.

Esto verifica el registro y su reemplazo real en el modelo nativo, todavía no widgets ni selección activa.
