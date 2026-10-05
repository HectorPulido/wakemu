# E10. Actualización equipment_set no crea entradas nuevas

Garantizar que creación/actualización de una hoja de equipo registre índices nuevos sin perder existentes.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

34, E04, E08. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Una build nueva anunciada tiene una entrada de equipo registrable, no un update dirigido a un índice inexistente.
