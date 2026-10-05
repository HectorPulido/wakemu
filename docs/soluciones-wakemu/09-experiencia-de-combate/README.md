# 9. No hay experiencia ni subida de nivel por combate

Conceder XP no nula según política configurable y refrescar todos los desbloqueos al subir nivel.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

10, 17, 33, 34 y E06. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

El recibo fija recompensa y versión; el nivel visible, XP y hojas nunca quedan parcialmente actualizados.

## XP cero en la ventana del personaje

[Diagnóstico específico y cálculo nativo](XP-CERO-EN-VENTANA.md): el total persistido de «Prueba Yopuka» coincide con el umbral del nivel 200; la barra muestra el avance dentro del nivel. Esto no cierra el problema de recompensas por combate.
