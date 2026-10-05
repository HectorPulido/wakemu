# 6. Cardo no llega a su etapa final

Recorrer todas las etapas válidas de una planta y conservar el progreso.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

5, 20, 27 y almacenamiento adicional. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Solo crece un recurso existente por una arista legal; un temporizador antiguo no recrea lo cosechado.

## Comprobación de etapas y acciones

[Scheduler detenido en 2 y tabla nativa de acciones](REVISION-RESPUESTAS.md).
