# 26. No se pueden añadir merkagemas

Transferir gemas propias entre inventario y ranuras del merkasaco sin duplicarlas.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

22, 23, 30 y 0. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Una UID está en inventario o slot, nunca ambos; retirada no elimina contenido ni concede gema nueva.

[Contratos ejecutados de inserción y retirada](REVISION-RESPUESTAS.md).
