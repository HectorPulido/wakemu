# 34. Builds personalizadas: desbloqueo tardío y hojas no seleccionables — prioridad alta

Completar desbloqueo, hojas, guardado, activación autoritativa, estadísticas/deck y persistencia de builds.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

9, 17, 22 y E04–E08. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Metadata, equipo, aptitudes, deck y selección comparten índice y revisión; el check visual Activa no prueba autoridad del servidor.

## Revisión posterior a tus respuestas

[Desbloqueo 51, cupo no permanente 24 y respuesta 13811 verificados](REVISION-RESPUESTAS.md). Esta revisión sustituye las dudas anteriores sobre esos contratos. Las referencias a casts son históricas o trabajo de otra sesión; no se continúan aquí.
