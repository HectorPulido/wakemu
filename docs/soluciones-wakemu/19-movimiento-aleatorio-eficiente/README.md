# 19. Todos los monstruos se mueven a la vez

Evaluar grupos cada 5 segundos con 25% independiente de moverse y varios pasos legales aleatorios solo donde hay jugadores.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

0, 3, 20. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Solo zonas presentes simulan; ninguna ruta mueve miembros durante combate/recolección o por celdas ilegales.

## Comportamiento comprobado

[Intervalo global, ausencia de tirada y codec de un paso](REVISION-RESPUESTAS.md).
