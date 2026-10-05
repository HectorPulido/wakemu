# 29. Mazmorras

Entrar, compartir salas, progresar y salir de mazmorras con encuentros/recompensas idempotentes.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

12, 14, 15, 25, 30, 33. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Una party comparte una instancia; sus salas/premios no se mezclan con otras ni se duplican al entrar.

## Composición y dificultades: prioridad de investigación

[Qué está y qué no está acreditado; tablas y pruebas necesarias](REVISION-RESPUESTAS.md). La arquitectura de instancias por sí sola no resuelve monstruos por sala ni multiplicadores.

- [Salas, ciclo de victoria/derrota, interfaz y grupos: cotejo concreto](SALAS-Y-CICLO-DE-INSTANCIA.md).

- [Contexto nativo, progreso personal y pruebas de retorno](INTERFAZ-Y-PROTOCOLO.md).
