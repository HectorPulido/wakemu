# 3. Los monstruos no se reproducen ni amplían grupos

Crear descendencia y ampliar grupos por reproducción o siembra, sin respawn automático independiente.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

2, 19, 20 y 0. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Cada nueva unidad tiene origen durable de siembra o reproducción; matar y esperar no genera unidades.

## Revisión de catálogo y política solicitada

[Familia 68, ausencia de is_boss, ruta de respawn y límites del crecimiento](REVISION-RESPUESTAS.md).
