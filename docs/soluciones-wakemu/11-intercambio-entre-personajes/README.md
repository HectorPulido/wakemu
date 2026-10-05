# 11. No se puede intercambiar con otros personajes

Intercambiar objetos y kamas entre dos cuentas con confirmaciones revisadas y transferencia atómica.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

0, 13, 22, 32, 34. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Suma de kamas y cantidades se conserva; una misma revisión requiere las dos confirmaciones actuales.

- [Contratos nativos, rechazo bilateral probado y transacción requerida](REVISION-RESPUESTAS.md).
