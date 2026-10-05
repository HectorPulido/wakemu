# Copia de características

La familia de efecto 1001 usa eWZ. No es el evento externo 1001: son identificadores en espacios distintos.

El cliente calcula en bbE, al aplicar: parámetro 0 identifica la característica (byte); el parámetro 1 es el porcentaje, por defecto 100. Captura primero el máximo del lanzador y después el valor actual. Usa multiplicación int32 con overflow, conversión float32 y redondeo estocástico UP.bt. El máximo INT_MAX se conserva como centinela; el actual sigue la multiplicación normal.

Al ejecutar, PA.or asigna el máximo y PA.on asigna el actual, respetando los límites propios de la característica. Retirar el efecto no revierte esas asignaciones.

Evidencia: ProbeNativeCopyCharacteristic.java ejecuta bbE real para porcentajes 100, 50 y 0, y cuatro casos de aplicación y retirada con PA nativo. Los tres tests de combat_copy_characteristic comprueban valores independientes, redondeo, centinela y overflow. El manejador común está conectado al dispatcher, con aplicación 13497 y retirada 13560 que conserva los valores copiados. El bloque adicional coincide con ij real (ejemplo 50036004). Falta el camino de registro y entrega de suscripciones para los usos que lo requieren; no implica funcionamiento completo en juego. Prueba de aplicación/retirada propia aprobada, además de tres pruebas de cálculo.
