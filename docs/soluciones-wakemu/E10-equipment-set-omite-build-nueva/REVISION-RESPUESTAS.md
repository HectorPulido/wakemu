# E10 — Colección de equipo y builds nuevas

## Cotejo actualizado

El usuario pidió revisar todo, sin decisiones adicionales. La función `equipment_set(character,original)` conserva el defecto histórico: solo recorre entradas existentes y no agrega un índice guardado ausente. Sin embargo, la búsqueda actual encuentra **únicamente su definición**, ningún caller Python del servidor. No es correcto atribuir automáticamente a esa función el bootstrap actual.

`wire.attribute_sheets`, invocado por replay 12393, usa ahora `equipment_registry` para personajes con nivel informado. Este constructor genera índices de `{0, *builds_guardadas}` y enlaza el registro a la identidad del personaje. La rama de template capturado queda para diccionarios sin nivel. Esto exige verificar que todos los callers suministren personajes completos, no solo identidad.

## Prueba actual

[Probe y hashes](probe-rutas-actuales.json): personaje sintético 12345 con build 2 y equipo vacío nativo válido; entrada original solo build 0. `equipment_set` produce índices **[0]**; `equipment_registry` produce **[0,2]**. Se analizaron directamente las entradas protobuf. No se ejecutaron decks ni hechizos, GUI o mutaciones SQL.

El consumidor nativo `cia` de 12393 decodifica registros mediante `fpi.eO`, obtiene cada identidad de personaje (`fpl.KU`) y los registra mediante `fpo.a(account,character,registry)`. El equipo se consulta independientemente de los metadatos de build: mostrar una fila no demuestra que su hoja de equipo esté registrada.

## Solución concreta y alcance restante

Usar un único constructor autoritativo para bootstrap y actualizaciones completas de equipo; retirar o delegar el helper obsoleto durante implementación, después de revisar consumidores externos. No modificar el template para agregar índices manualmente. Conservar separación entre índice de build, identidad de personaje y cuenta del registro.

Construir las cuatro colecciones desde la misma revisión persistida. Evitar anunciar una build sintética con metadatos/aptitudes y omitir su equipo: actualmente `build_set` y `aptitude_registry` incluyen índice 1 aunque no esté guardado, mientras `equipment_registry` incluye solo 0 y guardadas. Esa discrepancia sigue explicando un riesgo de fila visible sin hoja; el probe de índice 2 no la resuelve.

Tras guardar una build nueva, comprobar el consumidor de 12284 y el registro actualizado; tras eliminar, respetar el consumidor nativo analizado en E07. Bootstrap de reconexión debe reconstruir índices existentes desde DB/journal sin resucitar tombstones. La selección activa requiere autoridad persistida del issue 34, no forzar 0 al serializar metadatos.

Faltan captura gráfica nueva, equivalencia tras reconexión y comprobación de los listeners de actualización en GUI. Se corrige el diagnóstico de ruta actual sin afirmar resuelto el recorrido completo. No se aplicaron fixes.

## Semántica de reemplazo comprobada

`fpo.a(account,character,fpl)` ejecuta `Table.put` sobre el par cuenta/personaje: **reemplaza el objeto de registro completo**, no mezcla hojas con el anterior. Después notifica listeners `fpp.a(account,newRegistry)`. Una prueba Java offline instanció un registro propio, registró dos personajes y reemplazó el primero: el lookup devolvió exactamente el objeto nuevo y conservó el del segundo personaje. No se utilizó el singleton del cliente vivo ni se cambiaron partidas.

Implicación: el cuerpo 12393 debe contener la colección completa del personaje que actualiza. Enviar solo una hoja como si fuera un delta sustituiría el registro y omitiría las otras. Omitir otro personaje del mensaje no lo elimina automáticamente de `fpo`: las entradas anteriores para otros pares permanecen. El borrado de una build dentro del mismo personaje debe quedar reflejado en el registro nuevo completo o en la operación nativa dedicada de E07; no esperar que un merge elimine índices ausentes. Falta validar los listeners con GUI, pero la semántica básica de reemplazo ya está comprobada por código y ejecución nativa.
