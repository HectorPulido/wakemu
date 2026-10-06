# 19. Todos los monstruos se mueven a la vez

Evaluar grupos cada 5 segundos con 25% independiente de moverse y varios pasos legales aleatorios solo donde hay jugadores.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**Solucionado totalmente**: movimiento independiente confirmado por el usuario tras la recarga; política PostgreSQL de intervalo, probabilidad y pasos implementada. La reducción de locks compartidos sigue pendiente en rendimiento0. Ver [implementación actual](IMPLEMENTACION.md).

## Dependencias

0, 3, 20. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Solo zonas presentes simulan; ninguna ruta mueve miembros durante combate/recolección o por celdas ilegales.

## Comportamiento comprobado

La [revisión anterior](REVISION-RESPUESTAS.md) describe el diagnóstico histórico. La fuente actual evalúa cada monstruo con probabilidad independiente del 25 %, cada cinco segundos, y recorre entre uno y tres pasos legales. Una zona sin jugadores no consulta grupos ni emite movimiento; sigue habiendo una lectura global de política por ciclo.

El índice de aristas se prepara antes de locks y se reutiliza por mapa. Cada zona usa un snapshot de grupos. La planificación, el CAS PostgreSQL y la publicación permanecen bajo locks globales de grupos/recolección: es trabajo pendiente de rendimiento, y retirarlos exige preservar el orden con claims de combate y recolección. No se cambió esa sincronización durante esta revisión.

## Gate del 6 de octubre

`test_monster_wander test_combat_group_store test_monster_collect`: 38 pruebas OK en PostgreSQL aislado. Cubren política DB5s/25%/1–3 pasos, límites de tirada, caminos legales, grupos en pelea, exclusión de cosecha y CAS de grupos reclamados. La ausencia de consultas sin jugadores corresponde a `wander_location`; el daemon conserva su consulta global de política. No cubren una carrera concurrente real entre empezar a cosechar y mover un grupo ni acreditan latencia con locks globales.

## Reproducción fallida y corrección por individuo

El usuario creó cinco miembros con `!mob 4 8 5`: permanecieron quietos más de60s y al moverse conservaron la misma formación, acreditada por captura. Durante recolección no se movió ninguno. La tirada y el plan anteriores eran por grupo: una traslación rígida exigía aristas compatibles para todos y un miembro recolectándose bloqueaba el conjunto. La prueba previa por grupos no acreditaba movimiento independiente entre miembros.

Se implementó tirada25% por NPC y planificación individual de1–3 pasos, respetando ocupación de los otros miembros y posiciones candidatas ya planificadas. Recolección excluye únicamente al objetivo; pelea bloquea el grupo entero. Se conserva una única comparación/actualización atómica del roster por grupo y se publican paquetes tras confirmar. No cambia composición ni reglas de combate.

Estado: **Solucionado totalmente**. Gate actualizado:41 pruebas OK en PostgreSQL aislado; fuente recargada en Docker saludable. El usuario confirma «parece funcionar todo bien» tras la prueba completa solicitada de movimiento, recolección y cambio de zona. La formación rígida queda corregida; no se atribuye esta confirmación a orientación ni puño. La demora observada todavía requiere cotejar oportunidades de ruta y tiempos del daemon; no se explica automáticamente como una mala tirada. El usuario acepta movimiento conjunto dentro de un grupo si distintos grupos tienen ritmos distintos, pero la corrección individual también debe preservar ese comportamiento independiente.


## Cierre confirmado por el usuario

El usuario volvió a probar el movimiento y confirmó el cierre el6 de octubre. La optimización de locks del daemon corresponde al issue0; no mantiene abierto el comportamiento funcional19.
