# 33. Rendirse deja bloqueados nuevos combates y transporte

Finalizar abandono una vez y liberar sesión/grupo aun con continuación nativa flag 0 observada.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

9, 10, 14, 21. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Abandonar no concede XP/kamas/drop; toda reserva y referencia de sesión quedan liberadas una vez.
