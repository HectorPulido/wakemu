# Solución propuesta — 17

Permitir asignaciones válidas y obtener estadísticas deterministas al subir, bajar o restaurar puntos.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Construir réplica numérica

Tomar personaje nuevo con nivel/XP coherentes; registrar puntos por categoría, hoja activa, equipo y todos los modificadores. Aplicar secuencia A→B→A y comparar estadísticas absolutas, no solo deltas. El contexto nuevo reporta resultados distintos al aumentar/bajar; todavía falta un par de hojas/capturas que lo reproduzca exactamente.

## 2. Verificar presupuesto y nivel efectivo

Usar aptitude-rules budgets/concesión_levels y máximos de bonus. Decodificar 12772 con nivel de hoja (-1 real o nivel limitado) y distinguir puntos inexistentes de codec inválido. Resolver E06 antes de convertir una hoja antigua en inválida por subir el personaje.

## 3. Definir evaluación pura y orden

Recalcular desde stats base + equipo + aptitudes + modificadores nombrados; nunca usar stats ya efectivas como base del próximo guardado. Especificar porcentajes, orden y redondeo, caps y efectos no soportados. Mismo estado/versión da el mismo resultado, independientemente de cuántas veces se haya editado.

## 4. Compartir build activa y HP

Resolver una única build para equipo/aptitudes/deck según 34. Guardar allocations y versión antes del refresco; preservar HP parcial al cambiar máximo sin curación acumulativa. Quitarlas restaura exactamente máximos base salvo otros modificadores; no resetea daño real ni revive.

## 5. Sincronizar resultado autoritativo

ACK devuelve hoja canónica y snapshot propio con orden native probado, evitando doble bonus del preview local. Un rechazo restaura la hoja anterior sin codec 13713 inválido. Log de cálculo registra fuentes y hashes, no secretos, para comparar A→B→A y reconnect.

## 6. Aceptar la reversibilidad

Probar puntos 0/1/máximo por categoría, porcentajes y equipo compartido; repetir guardado idéntico no cambia resultados. Comparar evaluación explícita de secundaria y ruta normal; registrar diferencias debidas a selección ausente por separado de fórmula matemática.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Mismo estado produce mismas estadísticas; volver a una hoja previa revierte bonus sin borrar daño real.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
