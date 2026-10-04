Familia 877: mínimo de vida (eWV)
================================

Evidencia offline del cliente instalado: eVi registra 877 con eWV(ffw.sgC).
eWV.C lee valor parámetro0 y parámetro1 opcional ==1 para porcentaje; utiliza
GS.C(float(int32(maximum*value))/100), techo para positivos y truncado para
no positivos. No copia el valor del evento con parámetro -1.

eWV.c consulta PA.aYW (mínimo efectivo). En aplicación calculada bbs=true
asigna PA.os(value), y guarda value=minimum_after-minimum_before. La rama de
reaplicación bbs=false suma el valor serializado al mínimo efectivo. bbR resta
ese delta. fff.os asigna mínimo bruto, limita al máximo bruto, eleva corriente
si queda por debajo del mínimo y no la reduce al retirar el mínimo.

Implementación común: combat_minimum_resource.py, factory877 y retirada eWV
en NativeStatHandler; se exige snapshot bruto/efectivo completo y mutabilidad
conocida. El paquete 13497 conserva UID, baseUID, referencia, caster, target,
valor delta y reloj nativo. Retirada 13560 conserva el mismo efecto propio.
No se agregan datos adicionales: eWV no declara AdditionalDatas propias.

ProbeNativeMinimumResource.java ejecuta eWV y fff reales; confirma mínimo1,
clamp100, retirada sin daño, delta real y redondeo GS.C. Pruebas Python cubren
transición, aplicación/retirada con paquetes y rechazo de familia desconocida.
No hay comprobación visual ni reinicio del servidor en esta tarea.
