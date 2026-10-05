# E09. Hit Redis conserva lecturas SQL e inicializaciones repetidas

Separar migraciones/hidratación del camino caliente y evitar SQL completo después de un hit válido.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

0, 21, E03. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Una cache válida reduce SQL sin perder ownership, revocación o mutaciones pendientes.

## Trace actualizado

[Conteos SQL, persistencia Redis y shutdown cotejados](../00-rendimiento-y-redis/REVISION-RESPUESTAS.md).
