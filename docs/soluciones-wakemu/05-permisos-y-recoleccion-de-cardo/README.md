# 5. Cardo dice que el recurso pertenece a otra persona

Permitir recolección legal y emitir rechazos que correspondan al estado real del recurso.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**En revision.** El encoder del servidor enviaba `creation_time` en el campo nativo `ownerAccount`, haciendo que plantas y árboles públicos parecieran ajenos. Se corrigió el campo a `0`; la fecha sigue persistida para crecimiento. El mismo encoder publica nuevas plantas y snapshots al entrar al mapa. Regresión y gate de plantación: **18/18 pruebas OK** en Docker con PostgreSQL aislado, incluidos paquetes reales de cardo60/fresno139 y snapshots. Esta modificación aún no se ha recargado.

Se exportaron desde los datos nativos las acciones de flora para las 533 referencias, asociadas a sus etapas, con oficio, nivel mínimo, duración, referencias de producto y criterios. El catálogo facilita validar qué acción pertenece al recurso y etapa actuales.

La solución completa sigue pendiente: falta el handler de cosecha vegetal `12995`, la ocupación y su respuesta nativa, la concesión durable de recompensas y la transición/regeneración del recurso. El catálogo no acredita cantidades ni probabilidades de producto ni la XP de oficio; véanse los [límites de la exportación](REVISION-RESPUESTAS.md).

## Dependencias

1, 6, 8, 24. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Solo una cosecha por transición de recurso; ocupación temporal y propiedad no se confunden.

## Causa general comprobada

[Fecha enviada como ownerAccount: afecta plantas y árboles](REVISION-RESPUESTAS.md).
