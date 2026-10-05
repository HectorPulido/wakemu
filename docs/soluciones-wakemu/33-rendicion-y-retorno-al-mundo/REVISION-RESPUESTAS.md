# Revisión actual — rendición y retorno

## Corrección observada en el checkout

El cotejo histórico indicaba que el caller exigía flag verdadero. **El código actual ya no lo exige**: `combat_abandon.return_to_world` valida propietario, fase finished, winner=None y el ID de combate mediante`combat_results.continuation`, aceptando ambos booleanos. No atribuir el fallo antiguo a estos bytes ni afirmar que el servidor vivo los haya cargado. No se modificó código durante esta revisión.

Los cuatro tests actuales de abandono pasan. En SQLite desechable se prepararon combates distintos para flags0,1,2:0 y1 retornan,2 se rechaza; repetir el retorno válido no aplica de nuevo; hay un recibo de salida de salud y cero premios. [Resultados y hashes](probe-flags-retorno-actual.json). Son pruebas del servicio con combate sintético, sin GUI ni hechizos.

`prepare` ahora emite12238 con flag de retirada false y listas perdedores/ganadores; conserva resultado autoritativo de abort, sin premio. Eso evita la rama nativa que retiraba un participante y terminaba demasiado pronto para limpiar la UI. El dispatcher12925 restaura posición/transportes, termina la reserva del grupo, vuelve a publicar el mundo, finaliza checkpoint y pone referencias locales de combate aNone.

## Brechas vigentes

`_participant` todavía exige un único actor controlado: no implementa rendición parcial multijugador. El resto del equipo no debe cerrar cuando sale uno. La solución necesita transición por participante, retirada del turno/readiness, elegibilidad de recompensa y cierre del combate solo al quedar sin participantes elegibles de ese equipo. Conservar IDs y callbacks de cada conexión.

La salida del dispatcher depende de12925. No se encontró en esa ruta un timeout de retorno que libere referencias si el cliente no envía el callback. `fight_checkpoint_store.recover_interrupted` marca active como aborted al arrancar, pero no demuestra restaurar las conexiones/posiciones o reservas de un proceso todavía vivo. Persistir outcome y estado de salida por participante, y hacer el cierre de reservas idempotente independientemente del ACK gráfico; el ACK solo confirma que puede reenviarse el bootstrap a ese cliente.

Falta repetir GUI con esta versión cargada, abandono sin callback/desconexión, transporte posterior y combate con dos participantes. La política de penalización HP no se acredita como oficial: el módulo conserva daño autoritativo y no concede premios. No dar el issue por resuelto íntegramente por pasar los tests o corregir el flag.
