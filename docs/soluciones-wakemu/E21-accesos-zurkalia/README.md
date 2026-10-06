# E21 — Accesos de Zurkalia a Astrub y arenas

## Estado

Reportado por el usuario el 6 de octubre de 2026. Pendiente de reproducción y cotejo del servidor; no se considera solucionado.

## Síntomas

En Zurkalia, usar el acceso «Astrub» no permite bajar a Astrub. Tampoco funcionan las entradas a las arenas. La captura muestra el personaje junto al acceso Astrub con la acción «Utilizar» disponible. No hay evidencia aún de qué respuesta produce cada entrada.

## Investigación requerida

- Capturar por separado la petición de «Utilizar» en Astrub y cada arena: opcode, identificador del interactivo, mapa, instancia y coordenadas.
- Cotejar el catálogo nativo del interactivo y su destino con el handler del servidor; comprobar condiciones de acceso, resolución de instancia y posición válida de llegada.
- Revisar si se rechaza, se ignora o se inicia un traslado incompleto. No atribuirlo a permisos sin comprobarlo.
- Para arenas, verificar además creación y cierre de instancia, entrada individual y en grupo, y regreso a Zurkalia.

## Criterios de aceptación

Astrub carga el mapa y posición de destino correctos, permite caminar y conserva la ubicación al reconectar. Cada arena permite entrar y salir con un estado coherente; las restricciones válidas producen una respuesta nativa visible. No debe quedar el personaje entre mapas o en combate residual.

La causa y la solución específica se añadirán tras cotejar código y paquetes.

## Reproducción del usuario y logs

El usuario pulsó Astrub y todas las entradas de arena, esperando diez segundos: la pantalla parpadea, pero permanece en Zurkalia; no pudo probar el retorno. Los logs del boot `5485e527a14848ecaf55a3634f464c96`, actor 1, mapa 967, registran opcode 12296 rechazado con `Authoritative source interaction not allowed` a 05:52:01, 05:52:32, 05:52:35 y 05:52:37 UTC. El rechazo ocurre en la validación de interacción de origen, antes de confirmar el traslado; todavía falta identificar por qué esa validación falla.

Por instrucción del usuario, se registra el problema sin adelantarlo a los issues prioritarios.

## Catálogo cotejado

`server/protocol/native-generic-teleporters.json`: Astrub usa origen 25358 en (1,-15,26), destino 2221 → mapa 527, llegada (-21,35,8). Arenas cercanas: 25390 → 2231/mapa970, 25391 → 2232/mapa971 y 25397 → 2235/mapa975. Esas rutas tienen criterio vacío, costos cero, `cyZ=-1` y llegada transitable verificada.

`teleporter_approach.callback` exige que la coordenada XY exacta del interactivo esté en `Movement.approved`. Las posiciones registradas son vecinas. Esto localiza el rechazo; falta cotejar la semántica nativa de aproximación antes de modificarlo. No se ha introducido un radio arbitrario ni implementado una solución.
