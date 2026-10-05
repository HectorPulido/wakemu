# 14. No se puede entrar al combate de otra persona

Unir jugadores durante colocación a un encuentro compartido ya existente.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

12, 15, 16, 18, 31, 33, 34. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Todas las sesiones ven un único encuentro; entrar tarde no altera sus actores ni su turno.

[Servicio compartido, solicitud nativa y límites](REVISION-RESPUESTAS.md).
