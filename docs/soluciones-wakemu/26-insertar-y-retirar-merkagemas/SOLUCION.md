# Solución propuesta — 26

Transferir gemas propias entre inventario y ranuras del merkasaco sin duplicarlas.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Separar rearrange de inserción

rearrange_rooms mueve gemas existentes y no consume inventario. Los encoders ejecutados identifican 12177 para añadir y 13090 para retirar; ver [layouts y semánticas pendientes](REVISION-RESPUESTAS.md). Capturar sus respuestas y sustitución; documentar UID/tipo/slot primario/secundario. La gema fija inicial debe permanecer protegida; conocer GEM_TYPES no prueba protocolo de nueva inserción.

## 2. Validar permisos y compatibilidad

Solo dueño/ACL autorizada, sesión merkasaco vigente y UID propio. Comprobar tipo de gema, room_index 0–8, conflictos entre primaria/secundaria, capacidades y restricciones del layout. Reserva concurrente evita equipar/vender la misma gema en otra ruta.

## 3. Diseñar unidad en layout

Persistir gema instalada con UID y referencia y estado enabled de room, excluyéndola del inventario físico. Si está apilada dividir una unidad con propiedades. La misma UID no puede ocupar dos slots ni seguir visible como item disponible.

## 4. Confirmar entrada/salida atómicamente

Insertar consume/mueve unidad y habilita sala con recibo. Retirar comprueba muebles/personajes/plantas, espacio de inventario y destino; devuelve exactamente la misma unidad o regla documentada. Si no hay espacio, rechaza antes de deshabilitar sala; no borra contenido para forzar retirada.

## 5. Actualizar mapa y recovery

Layout nativo, salas, ocupación y objetos se publican en orden probado. Mover actor a sala segura si pierde suelo, solo conforme a regla. Reconnect/reabrirmerkasaco/flush conservan personalización y no duplican gema inicial sintética.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Una UID está en inventario o slot, nunca ambos; retirada no elimina contenido ni concede gema nueva.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
