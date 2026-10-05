# Issue 31 — Celdas de colocación: revisión del código actual

## Respuesta y alcance

El usuario respondió «Revisa todo. Nada que decidir». No se requiere otra decisión para inspeccionar capacidad, distribución o integración. Se preserva esa respuesta en `FALTANTES.md`. Este cotejo no modifica el servidor ni prueba hechizos.

## Ruta real e implementación actual

El handler de ataque `13130` en `local_game_server.py` obtiene los miembros del grupo y llama a `local_arena` con posiciones reales. Esa función selecciona terreno exportado del mapa, genera **12 celdas por equipo** y entrega tanto flags serializados como `placement_cells` al bootstrap. El generador tiene default **6**, pero la ruta real lo sobrescribe con **12**: citar solo el default describe incorrectamente el comportamiento actual.

`combat_bootstrap.prepare` usa las celdas recibidas del arena. Su fallback de una celda por actor existe, pero no se ejecuta cuando este caller suministra `placement_cells`. El inicio de combate sigue condicionado al flag global de pruebas; generar celdas múltiples no habilita por sí solo ingreso de grupos ni de otros jugadores.

El algoritmo conserva posiciones ocupadas, bloquea semillas enemigas al recorrer aristas dirigidas, ordena candidatos por distancia y coordenadas y alterna equipos. Es determinista, sin seed aleatoria: la misma situación produce el mismo layout. Un terreno pequeño entrega solo capacidad disponible; más actores que el límite conservan sus posiciones. No inventa pisos ni conexiones.

## Prueba con terreno real

[Probe y hashes del código](probe-terreno-real-actual.json): tres pares adyacentes distintos tomados del export real del mapa **1134**, sobre altura **70**. Cada selección alcanzó **45 celdas** y generó **12 + 12** plazas. Se comprobó ausencia de solapamiento, pertenencia al terreno, determinismo y conservación de ambos recuentos tras serializar y decodificar la topología Python. No son coordenadas inventadas ni un grid sintético.

Los cinco tests existentes de `test_combat_placement_cells.py` habían pasado en esta auditoría: incluyen mapa pequeño, escaleras, más actores que cupos y preparación de dos jugadores. Este probe no ejecutó GUI, consumidor Java ni varios jugadores conectados; tampoco acredita todos los mapas. El export 1134 contiene topología, no layouts oficiales de colocación.

## Solución concreta del servidor

Eliminar la discrepancia entre default documental y caller usando un único parámetro versionado en DB: capacidad de colocación, separado del máximo de integrantes del grupo. Validar 1–127 y la capacidad conjunta del protocolo; conservar todas las posiciones iniciales válidas. Registrar capacidad efectiva y revisión por combate. Véase [políticas en DB](../PARAMETROS-SERVIDOR-EN-DB.md).

Para variar layouts repetidos, seleccionar candidatos alcanzables con RNG determinista por identidad durable de combate y revisión de política, persistiendo el resultado antes de publicarlo. No regenerar al reconectar o al reintentar un paquete. Mantener disjunción, terreno válido, alturas únicas y reservas de participantes. La cantidad de plazas no es una regla oficial demostrada: 12 es la política actual del caller.

Cotejar ingreso multijugador contra estas mismas reservas: reservar una celda libre atómicamente, rechazar equipo lleno con respuesta nativa y evitar que dos conexiones ocupen la misma plaza. No basta con que una fixture construya dos actores. Faltan reproducción gráfica y medición de variedad en varias zonas; no se declara cerrado el flujo.
