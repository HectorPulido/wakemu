# E06. Subida de nivel parcialmente confirmada con hoja fija inválida

Hacer atómica la transición de nivel/XP/hojas/salud y definir semántica de hojas limitadas.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

9, 17, 34. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Nivel/XP y hojas compatibles cambian juntos; un evaluador no puede fallar después de dejar media transición confirmada.
