# 18. No se puede elegir hacia dónde mirar en colocación

Permitir elegir dirección legal durante colocación, sin consumir recursos ni exigir turno activo.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

14, 31, 33. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Girar en colocación cambia solo facing de actor propio y no debita AP/MP ni inicia un turno.

[Cotejo nativo y ocho pruebas por fase](REVISION-RESPUESTAS.md).
