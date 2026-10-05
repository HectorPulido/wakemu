# Diagnóstico — 4

## Contexto registrado

**Confirmado:** `client/tools/java/OpenPlantingAgent.java` reemplaza `dev.am` por un retorno constante `1` y `ffY.C` por `100`. El lanzador activa la política abierta por defecto. En el servidor, completar una plantación válida usa resultado exitoso sin una tirada probabilística. El retorno `1` por sí solo no acredita la unidad del texto mostrado, pero sí que el cliente dejó de calcular su valor original.

**Posible solución:** distinguir modo de pruebas y modo normal; mostrar una probabilidad coherente con la decisión autoritativa del servidor. Suelo, clima y reglas territoriales deben alimentar el mismo cálculo. **Validación:** probabilidades 0%, 1% y 100% con RNG controlado y resultados estadísticos suficientes.

## Lectura actual

El contexto enviado y la autorización de familia son piezas existentes; deben cotejarse con la probabilidad efectiva y el render nativo. El porcentaje visual no demuestra la tirada del servidor.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Fórmula de probabilidad, escala y redondeo de esta versión.
- Campos del contexto nativo y efecto del override en el perfil del usuario.
- Consumo de semilla y XP cuando falla la tirada.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
