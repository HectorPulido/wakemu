# 18. No se puede elegir hacia dónde mirar en colocación

Permitir elegir dirección legal durante colocación, sin consumir recursos ni exigir turno activo.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Corrección implementada y cargada en Docker healthy. Trece pruebas de orientación y checkpoint pasan; consumidor nativo cotejado. Validación visual y sincronización multijugador pendientes. Ver [evidencia de implementación](IMPLEMENTACION.md).

## Dependencias

14, 31, 33. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Girar en colocación cambia solo facing de actor propio y no debita AP/MP ni inicia un turno.

[Cotejo nativo y ocho pruebas por fase](REVISION-RESPUESTAS.md).

## Regresión reproducida y corrección del 6 de octubre

El usuario confirma que cuatro flechas y teclado no cambian orientación durante colocación. Logs06:15:17–06:15:35 UTC: peticiones13655 recibidas y rechazadas por ausencia de handler en el estado actual. El dispatcher exigía `fight_messages`, que no existe antes de Listo; el codec y validador standalone sí soportaban placement.

Se cambió la guardia a pelea existente y se construye el runtime de colocación mediante el helper existente. Se conserva el runtime solo después de validar la orientación. No cambia casilla, PA, PM ni reglas de hechizos. Estado: **Cambio hecho no confirmado**; faltan gate integrado, recarga y aceptación visual completa.

La transición de colocación a Listo pasa `previous_native_action_id` al preparador y lo valida antes de construir los paquetes de inicio. No basta copiarlo después: esos paquetes ya habrían reutilizado IDs. El preparador inicia su contador nativo con el último valor de colocación; el contador lógico mantiene su contrato. Falta comprobar continuidad y agotamiento mediante el gate integrado.

## Gate integrado aprobado

53 pruebas OK en Docker con PostgreSQL aislado: `test_combat_orientation test_placement_deadline test_combat_melee test_combat_trigger_identifiers test_combat_trigger_indirect test_combat_spell_transaction`. Incluye ejecución del handler real13655 en las cuatro direcciones, preparación de Listo, puño, fin de turno y ACK, con IDs nativos únicos; agotamiento rechaza antes de activar la pelea. Cambio aún sin recargar mientras el usuario prueba movimiento; aceptación visual pendiente.
