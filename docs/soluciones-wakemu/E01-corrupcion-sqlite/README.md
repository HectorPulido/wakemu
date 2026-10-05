# E01. Corrupción histórica de SQLite interrumpe crecimiento

Asegurar integridad y recuperar una copia consistente antes de confiar en progreso/ecosistema.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

0, 2, 3, 6, 20. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Recovery nunca inventa objetos/progreso; la copia reparada se valida antes de sustituir la autoridad.

[Evaluación SQLite/PostgreSQL y migración concreta](SQLITE-VS-POSTGRESQL.md): recomendación de PostgreSQL para el servidor multijugador; sin migración aplicada ni benchmark comparativo.

[Migración definitiva: 27 tablas, tipos, relaciones, locks y cutover](MIGRACION-POSTGRESQL-TABLAS.md). Sin retrocompatibilidad SQLite, conforme a la instrucción del usuario.
