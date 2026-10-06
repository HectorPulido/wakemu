# E07. Borrado nativo de build sin handler

Implementar eliminación nativa con fallback activo y sin destruir objetos referenciados.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Implementación del servidor en curso: borrado, selección y salud atómicos en PostgreSQL; handler13169 conectado en fuente, con ACK12837 de éxito/rechazo. Pruebas delegadas a Luna y carga/aceptación visual pendientes. Los apartados históricos del journal Redis fueron reemplazados por E01. Ver [implementación](IMPLEMENTACION.md).

## Dependencias

34, E04, E05, E08. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Eliminar una hoja no elimina sus objetos; selección válida y controles se restauran en todas las salidas.

## Borrado real confirmado el 6 de octubre

El usuario eliminó «nanana», build3 activa, y confirmó que siguió eliminada tras volver a entrar. Las capturas muestran contador2/24 y build predeterminada activa. PostgreSQL conserva únicamente hojas1/2 y selección0; log `build_deleted` a05:36:06 UTC acredita handler13169, índice3 y fallback0. La validación visual se suma a la regresión transaccional de borrado, rechazo y conservación de inventario. E07 queda resuelto; esta prueba no acredita los consumidores de combate pendientes de E05.
