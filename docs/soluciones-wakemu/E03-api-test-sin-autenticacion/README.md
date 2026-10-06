# E03. API de pruebas ejecuta antes de autenticar

Autenticar y autorizar todas las rutas de prueba y tareas, conservando separación de roles.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**Resuelto y verificado en Docker** para E03; controles de rutas, jobs y principal cron probados. [Implementación, pruebas, operación y límites](IMPLEMENTACION.md).

## Dependencias

32, 21, 0. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Ningún endpoint de prueba elude autenticación por estar antes de la rama común.

## Evidencia adicional ejecutada

[Cotejo posterior a las respuestas del usuario](REVISION-RESPUESTAS.md).
