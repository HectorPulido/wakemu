# 16. No se pueden ver los combates

Mostrar combates vivos y permitir observación sin autoridad para actuar.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

14, 15, 33. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Observar nunca concede control; un cliente lento o desconectado no bloquea el combate observado.

[Salida nativa y separación de subscriptions](REVISION-RESPUESTAS.md).
