# Salida de colocación tras rechazo de Listo

Incidente: actor14, combate935312774. Los registros de servidor muestran:

- 2026-10-05T16:46:58.564253Z y16:47:17.567046Z: Listo rechazado por
  `Unsupported HasStateFromUser actor selector`.
- 16:50:20.827936Z y16:50:24.246667Z: solicitudes13952 para rendirse.
- Ambas terminan en `request_rejected: No handler for this opcode in the current session state`.

La causa de la salida bloqueada es independiente del criterio: la colocación
ya tiene un Fight, pero RuntimeMessages sólo se asignaba tras inicializar Listo
con éxito. El handler13952 exigía RuntimeMessages y por ello nunca alcanzaba
combat_abandon.prepare, que sí admite la fase placement. La rama genérica
registraba el rechazo sin el aviso de chat del handler de rendición.

Corrección común: el handler atiende13952 de una sesión cargada; recupera un
RuntimeMessages únicamente cuando existe una colocación sin runtime. Valida la
identidad si ya existe un runtime, conserva sus contadores y no reconstruye
combates activos. Asigna el nuevo runtime sólo tras la persistencia exitosa de
la cancelación. Emite el cierre12238 y13420 mediante la frontera habitual de
identificadores, y mantiene el retorno12925. Los rechazos, incluido no tener un
combate, pasan por el aviso de chat seguro y el log específico de rendición.
El criterio HasStateFromUser sigue siendo responsabilidad de otro cambio.

Validación: seis pruebas de combat_abandon pasan, incluida una inicialización
Listo realmente rechazada por callback, posterior cancelación sin runtime,
entrega12238/13420 y retorno12925 con salud preservada. También se comprueba
que no se sustituyen contadores activos ni se acepta un runtime de otro Fight.
Compilación de main y combat_abandon pasa. No se ha reiniciado el servidor ni
se ha controlado la sesión del usuario; la entrega GUI queda pendiente del
despliegue coordinado.

```sh
PYTHONPATH=server:server/tests python3 -m unittest test_combat_abandon -q
python3 -m py_compile server/local_game_server.py server/wakfu_server/combat/combat_abandon.py
```
