# Diagnóstico — 17

## Contexto registrado

Extra: Ademas tambien cuando si se puede usar la aptitud, parece que el calculo se hace de manera incorrecta, de tal manera que cada vez que subo o bajo las caracteristicas el resultado final es totalmente diferente

**Confirmado:** sí existe validación/persistencia de aptitudes mediante `12772`, `items/builds.py` y `characters/aptitudes.py`. La XP cero puede impedir obtener nuevos puntos. El log contiene rechazos `Allocated aptitudes are unavailable`, criterios de equipo no implementados e identidades de slots adicionales no implementadas; algunos pueden corresponder a una versión anterior del código.

**Posible solución:** correlacionar el rechazo concreto con nivel, presupuesto por categoría y hoja enviada; distinguir puntos inexistentes de un fallo de protocolo o efectos no soportados. **Validación:** asignar puntos disponibles, rechazar sobreasignación y comprobar efecto, panel y persistencia.

## Lectura actual

La validación y presupuesto de aptitudes ya existen; comprobar selección activa, persistencia y recálculo. El plan debe preservar rechazo antes de mutación y evitar bonus acumulados.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Hojas y valores concretos antes/después del cálculo errático.
- Orden de porcentajes/redondeo/caps acreditado por efecto nativo.
- Regla de restitución de puntos/respec y nivel modulado.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
