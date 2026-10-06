# 1. Las semillas solo disminuyen al reconectar

Consumir exactamente una semilla por plantación aplicada y mostrar la cantidad correcta sin reconectar.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Implementación del **servidor** cargada: delta de inventario por plantación y cooldown de extracción en PostgreSQL. [Evidencia y61 pruebas](IMPLEMENTACION.md); comprobación gráfica posterior pendiente. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

4, 5, 6, 22 y persistencia de 0. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

cantidad_antes = cantidad_después + consumo_confirmado; nunca dos consumos por un resultado repetido.

- [ACK nativo que consume semilla y límites de la prueba gráfica](REVISION-RESPUESTAS.md).
