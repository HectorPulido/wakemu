# Solución propuesta — 23

Equipar una unidad de un bolso apilado o rechazarlo sin romper inventario, mundo ni estadísticas.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Preservar el fallo demostrado

Usar capturas/logs del personaje 9 y UID reportado; mantener copia de estado anterior/posterior. El SQL seguía cantidades 5/5/3, nivel 1,XP0 y quick_check correcto mientras UI tenía mapa negro/HPabsurdo. Eso es desalineación de protocolo, no prueba de daño a HP ni origen de corrupción SQLite.

## 2. Corregir recuperación antes de aceptar stacks

cwY/chK13713 entrega bytes a biB.as para entidad completa; synchronization actual manda solo bolsas. Seguir E02: elegir serializer de entidad completa probado o carrier de inventario específico con orden seguro. No parchear la UI ni añadir header arbitrario a los bytes de bolsas.

## 3. Resolver elegibilidad del bolso

Clasificar referencia Sadida negro, bag type, criterios y capacidad; ordinary rechaza especializados y quantity!=1. Definir soporte de restricciones del bolso antes de aceptarlo universalmente. La condición no implementada devuelve rechazo canónico seguro sin consumir stack.

## 4. Planificar split transaccional

Reservar UID server-authoritative para una unidad, copiar todas las propiedades de 22, conservar quantity-1 del original y validar slotbolso/capacidad. Equipar, crear contenedor y vincular unidad en una sola transición; espacio insuficiente o UID duplicado revierte todo.

## 5. Publicar estado válido

Actualizar cantidad original, unidad equipada, contenedores/capacidad y registro nativo en orden probado. Rechazo restaura movimientos optimistas; éxito no conserva la unidad simultáneamente en bolsillo y bolso equipado. Cambiar bolso ocupado debe preservar contenido o rechazar antes de consumir.

## 6. Validar conservación y otras rutas

Comparar inventario/HUD/mapa tras éxito, rechazo, duplicado y reconnect. Ejecutar todos los handlers que comparten synchronization para no arreglar solo Sadida. Probar slots llenos y bolso viejo, no únicamente cantidad 3 de una referencia.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

La suma de unidades se conserva; ningún rechazo genera mapa negro ni características absurdas.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
