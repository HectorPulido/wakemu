# Implementación — bolso apilado

## Comportamiento

Equipar un bolso ordinario de cantidad mayor que1 separa exactamente una unidad dentro de la misma transacción. El stack conserva UID y posición, con cantidad reducida; el contenedor equipado recibe un UID nuevo del asignador compartido. Una unidad suelta conserva el UID original.

Se mantienen las comprobaciones de propietario, lease, contenedor fuente, nivel mínimo y slot libre. Repetir la misma petición con el slot ocupado falla antes de consumir otra unidad. El fallo usa la recuperación corregida en E02.

El servidor envía los carriers existentes: 12470 con delta -1 sobre el stack y 12919 con el contenedor de UID nuevo. No se cambia el cliente.

## Verificación

`PYTHONPATH=server python3 -m unittest server.tests.test_inventory_bags server.tests.test_inventory_resync server.tests.test_inventory_move -q`: **10 pruebas PASS**.

Referencia cotejada en los catálogos nativos: **12493, Bolso sadida negro**, capacidad10, nivel mínimo1, sin filtros de tipos ni criterios adicionales. La regresión usa ahora esa referencia exacta.

Regresión específica: stack3 → stack2 + bolso equipado; UID distinto; replay rechazado sin cambios; quitar el bolso y reabrir la DB conserva tres unidades y ambos UID. La regresión de E02 ahora provoca el rechazo con un slot ocupado, porque un stack en slot libre ya es válido.

Pendiente: aceptación visual del caso Sadida con su referencia exacta y continuación de operaciones. Las reglas de bolsos especializados o con criterios nativos siguen fuera del soporte de `ordinary`; no se declara compatibilidad con todo el catálogo.

Cambio cargado mediante reinicio autorizado de `world`; health HTTP vuelve a responder. La aceptación visual sigue pendiente y se delegó exclusivamente a Luna.
# Evidencia visual adicional

Audit Bags, personaje36 de cuenta de auditoría: equipar desde pila3 mostró pila2 y contenedor «Bolso sadida negro0/10», con mapa visible y60HP. Tras reconectar persistieron pila2, bolso equipado y bolsa inicial0/4. La retirada por UI no se completó: el intento de arrastre volvió al launcher y no permite acreditar retirada ni atribuir la salida a una causa. La posición cambió de(-12,-8,-1) a(-6,-4,0); requiere revisar logs, no se declara corrupción ni éxito del paso de retirada. Evidencia privada en `.runtime/local/review-continuacion-20261004/shortcuts/audit-bags-after-remove-drag.png`.
