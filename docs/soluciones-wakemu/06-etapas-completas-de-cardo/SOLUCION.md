# Solución propuesta — 6

Recorrer todas las etapas válidas de una planta y conservar el progreso.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Comprobar almacenamiento primero

Los errores históricos malformed pueden detener incluso la primera transición. Ejecutar verificación sobre copia consistente según E01, no reparar el mundo activo por sospecha. Separar BD sana con lógica limitada de BD dañada con scheduler que falla.

## 2. Extraer grafo de etapas por referencia

Para Cardo, enumerar etapas reales, acciones disponibles y duraciones. El código actual busca stage 1 y avanza a 2; no deducir que final=3 ni que todos los recursos usan etapas consecutivas. Asociar referencia/catálogo/version al grafo y definir etapa terminal/cosechable.

## 3. Persistir próximo cambio y reloj

Guardar etapa actual, tiempo restante/próximo cambio y revisión. Integrar pausa de 20 y modificadores de clima 27 según regla decidida. Al cosechar validar que la transición programada sigue aplicando al recurso; cancelar un timer obsoleto.

## 4. Procesar cada transición legal

Seleccionar recursos vencidos mediante índice de zona/fecha. Comparar etapa/revisión, aplicar una arista válida y programar la siguiente en la misma operación. Decidir explícitamente si un retraso del scheduler permite catch-up dentro de zona activa; límite de pasos evita bucles y saltos no visualizados.

## 5. Publicar y recuperar

Outbox de actualización nativa por etapa; bootstrap usa estado persistido actual. Repetir tick no vuelve a crecer ni regenera una planta cosechada. Al reabrir, restaurar siguiente transición y observar etapa final sin necesitar reconexión.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Solo crece un recurso existente por una arista legal; un temporizador antiguo no recrea lo cosechado.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.

## Comprobación de etapas y acciones

[Scheduler detenido en 2 y tabla nativa de acciones](REVISION-RESPUESTAS.md).
