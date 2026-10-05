# 17. No se pueden subir características

Permitir asignaciones válidas y obtener estadísticas deterministas al subir, bajar o restaurar puntos.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

9, 22, 28, 34 y E06. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Mismo estado produce mismas estadísticas; volver a una hoja previa revierte bonus sin borrar daño real.

## Defecto adicional reproducido

[E12: curación por alternar aptitudes, con diez casos aislados](../E12-curacion-al-alternar-aptitudes/README.md).
