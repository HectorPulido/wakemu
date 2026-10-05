# E03. API de pruebas ejecuta antes de autenticar

Autenticar y autorizar todas las rutas de prueba y tareas, conservando separación de roles.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

32, 21, 0. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Ningún endpoint de prueba elude autenticación por estar antes de la rama común.

## Evidencia adicional ejecutada

[Cotejo posterior a las respuestas del usuario](REVISION-RESPUESTAS.md).
