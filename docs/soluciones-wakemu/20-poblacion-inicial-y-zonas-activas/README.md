# 20. Pocos mobs iniciales, reproducción y pausa sin jugadores

Sembrar población inicial pequeña una sola vez y pausar simulación sin jugadores.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

2, 3, 19, 0. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Seeding una vez por zona/version; estado vacío no se rellena implícitamente al entrar.
