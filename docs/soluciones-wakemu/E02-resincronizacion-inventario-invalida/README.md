# E02. Recuperación de inventario 13713 serializa bolsas como entidad

Reemplazar el contrato de recuperación mal serializado para todos sus consumidores.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

23, 22, 26. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Toda respuesta se valida por su parser nativo; un rechazo no altera el estado visual de otros dominios.
