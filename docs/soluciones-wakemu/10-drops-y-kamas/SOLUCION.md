# Solución propuesta — 10

Entregar botín y kamas configurables, sin duplicación ni pérdida cuando falta espacio.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Separar kamas de loot

Confirmar default de kamas y ausencia de loot en los módulos. Activar importe fijo no implementa tablas de drop. Inventariar familias, referencias, cantidades, probabilidad y condiciones; no inferir botín desde items disponibles en catálogo.

## 2. Definir multiplicadores y RNG

Proponer multiplicadores independientes DROP_MULTIPLIER y KAMAS_MULTIPLIER. Acordar si drop multiplica probabilidad o cantidad, clamp y redondeo; registrar versión, draws y lista final por fight/participante. Reintentos no vuelven a tirar ni identifican otro objeto.

## 3. Validar recompensa e inventario

Antes de confirmar, verificar elegibilidad, límites de wallet, stack y capacidad. Para equipo, generar propiedades por unidad según 22. Inventario lleno necesita política durable de entrega pendiente/mensaje, no eliminar premios ni añadir un ítem en slot ocupado.

## 4. Confirmar wallet y objetos juntos

Reservar UIDs únicos, registrar recibo, sumar kamas y crear stacks/entregas en una transición. Para Redis primero conservar atomicidad de consumo/entrega y recovery; no conceder de SQL viejo. Recibo ya existente devuelve la lista final sin repetir inserciones.

## 5. Emitir resumen y deltas

Resultado de combate enumera exactamente premios confirmados o pendientes; wallet y notificaciones de inventario reflejan esa lista. Ordenar cierre y retorno al mundo para no perder productos. Reabrir/flush conserva UIDs, propiedades y balances.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Resumen=recibo=wallet/inventario; cada UID otorgado y cada kama se entregan una vez.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
