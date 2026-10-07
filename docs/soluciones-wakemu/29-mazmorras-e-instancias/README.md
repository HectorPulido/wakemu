# 29. Mazmorras

Entrar, compartir salas, progresar y salir de mazmorras con encuentros/recompensas idempotentes.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría e implementación parcial del **servidor**. La base durable de sesiones/miembros en migración 065, el resolvedor limitado a rutas verificadas y la transición atómica de roster en `maps/dungeon_transport.py`/`maps/dungeon_instances.py` están probados con PostgreSQL aislado. La entrada sigue desconectada del dispatcher: no hay caller para el evaluador de criterio/proximidad, no se emitió bootstrap de mapa y no se ha habilitado el acceso. Las pruebas no certifican el recorrido jugable.

**Estado funcional actual (2026-10-07):** el acceso normal candidato a Jalató está identificado (mapa 527, transportador 26842, destino 2504, plantilla 91). El servicio puede crear/reutilizar el run y trasladar toda la party a una instancia recién generada en una sola transacción, sin usar `cyZ` como `instance_id`. La migración 068 guarda el modo de servidor explícitamente, y el helper acepta solo `IsNeoServer()` y `not IsNeoServer()`. El cliente declara `server.group.isneo` con valor predeterminado `false`; el vínculo exacto entre el visitor del criterio y esa clave se infiere por su nombre y alcance de configuración, porque el visitor no está en los artefactos disponibles. Aún falta conectar el callback de proximidad y el dispatcher. No se abrió el acceso. Ver [diagnóstico actualizado](DIAGNOSTICO.md).

La regresión 12296 confirma que el transporte genérico mantiene el rechazo del criterio especial y no mueve al personaje. La prueba durable también confirma que el ID 91 no autoriza como ID de una instancia activa. El siguiente paso de integración sigue siendo una transición de party respaldada por autorización nativa, con el `instance_id` creado por el servicio.

## Dependencias

12, 14, 15, 25, 30, 33. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Una party comparte una instancia; sus salas/premios no se mezclan con otras ni se duplican al entrar.

## Composición y dificultades: prioridad de investigación

[Qué está y qué no está acreditado; tablas y pruebas necesarias](REVISION-RESPUESTAS.md). La arquitectura de instancias por sí sola no resuelve monstruos por sala ni multiplicadores.

- [Salas, ciclo de victoria/derrota, interfaz y grupos: cotejo concreto](SALAS-Y-CICLO-DE-INSTANCIA.md).

- [Contexto nativo, progreso personal y pruebas de retorno](INTERFAZ-Y-PROTOCOLO.md).
