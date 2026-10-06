# 23. Bolso Sadida apilado rompe la interfaz hasta reiniciar

## Validación manual confirmada

El usuario probó `!item 12493 3` con Audiluna y confirmó el comportamiento esperado: equipar una unidad del stack deja dos sin equipar, el bolso muestra capacidad e inventario/ficha permanecen válidos; reconexión conserva el resultado. Se considera resuelto el defecto reportado de equipar el bolso apilado. Esto no certifica la recuperación explícita13713 de E02, cuyo recorrido se prueba por separado.

Equipar una unidad de un bolso apilado o rechazarlo sin romper inventario, mundo ni estadísticas.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Resuelto en el servidor activo: separación transaccional y prueba manual del usuario acreditadas. Los documentos de diagnóstico conservan el contexto histórico.

## Dependencias

22 y E02. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

La suma de unidades se conserva; ningún rechazo genera mapa negro ni características absurdas.

## Implementación

Separación transaccional de una unidad implementada; diez pruebas PASS y aceptación manual confirmada. Ver [IMPLEMENTACION.md](IMPLEMENTACION.md).

El usuario confirmó que los tres casos solicitados pasaron. Estado en el índice: **Solucionado totalmente**; no queda una repetición manual del bolso pendiente.
