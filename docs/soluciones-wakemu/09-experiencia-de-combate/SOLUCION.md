# Solución propuesta — 9

Conceder XP no nula según política configurable y refrescar todos los desbloqueos al subir nivel.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Comprobar configuración efectiva

Leer variables del proceso elegido sin imprimir secretos y comparar WAKFU_LOCAL_FIGHT_XP con Compose. El valor inicial 0 desactiva XP aun existiendo el servicio. No cambiar el servidor compartido ni confundir configurar valor fijo con implementar fórmula por enemigos.

## 2. Definir base y multiplicador

Documentar XP base por victoria, nivel/familia/enemigos y reparto entre participantes; añadir XP_MULTIPLIER como propuesta, tipo/rango y redondeo exactos. Cero significa desactivado solo si se acuerda. Guardar versión de política en el recibo para que un retry tras cambio de multiplicador no cambie el premio.

## 3. Validar elegibilidad y confirmar

Usar recibo por fight_id/participante. Solo victoria elegible otorga; duelo/abandono/derrota siguen reglas explícitas. XP se actualiza atomizada con nivel, hojas necesarias y salud para evitar E06; validación debe terminar antes de commit parcial.

## 4. Actualizar nivel y colecciones

Calcular nivel a partir de XP nativa, procesar todos los umbrales atravesados y cap. Refrescar hechizos, aptitudes, builds y HUD en una secuencia nativa coherente. Compartir el servicio con !nivel conservando diferencias de autorización; no reenviar únicamente outside_progression.

## 5. Ordenar delta y resumen

13613 llama incremento de XP; emitir una vez antes del snapshot absoluto, como indica combat_xp_gain. Resumen, progreso propio y recibo tienen la misma cantidad. Un resultado repetido o recuperación no vuelve a emitir un delta sumable.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

El recibo fija recompensa y versión; el nivel visible, XP y hojas nunca quedan parcialmente actualizados.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
