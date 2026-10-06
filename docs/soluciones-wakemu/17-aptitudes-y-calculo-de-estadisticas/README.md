# 17. No se pueden subir características

Permitir asignaciones válidas y obtener estadísticas deterministas al subir, bajar o restaurar puntos.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**Solucionado totalmente**: el servidor actual guarda y valida aptitudes en PostgreSQL, recalcula la build activa y publica el refresco autoritativo. Gate actual: 58 pruebas OK; aceptación manual completa confirmada por el usuario. Los documentos de auditoría conservan el diagnóstico histórico y no describen necesariamente el código actual.

## Dependencias

9, 22, 28, 34 y E06. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Mismo estado produce mismas estadísticas; volver a una hoja previa revierte bonus sin borrar daño real.

## Defecto adicional reproducido

[E12: curación por alternar aptitudes, con diez casos aislados](../E12-curacion-al-alternar-aptitudes/README.md).

## Validación actual

Gate: `test_aptitudes test_builds test_build_capacity test_health test_health_tick_writes test_equipment_stats test_combat_equipment_return`: 58 pruebas OK en Docker/PostgreSQL aislado. El guardado12772 emite ACK12284, registro12393, aptitudes12103 y snapshot13046. Regresión integrada: HP1370/1470 con puntos →950/1050 sin puntos →1370/1470 al restaurar; conserva daño100 y persiste la hoja. No se modificaron efectos ni motor de hechizos. El usuario confirmó los ocho pasos de la prueba manual: un punto aumenta los cuatro dominios en5, dos en10; cierre/reapertura, alternancia, cambio de personaje y reinicio del cliente conservan la hoja sin acumular bonus. Reiniciar características devuelve puntos y estadísticas iniciales, y persiste tras cambiar de personaje.

Cotejo del servidor activo: boot `e0a3fd9658ce4e1db9c35ddf34bee516`, actor1; logs de guardado de hoja3 a06:05:20,06:06:16,06:07:16 y06:09:46 UTC y activación a06:06:52. PostgreSQL conserva hoja3 seleccionada, revision8. Estos eventos complementan la aceptación manual, sin sustituir lo observado por el usuario.
