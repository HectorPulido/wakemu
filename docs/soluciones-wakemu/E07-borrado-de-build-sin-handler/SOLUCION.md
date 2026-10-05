# Solución propuesta — E07

Implementar eliminación nativa con fallback activo y sin destruir objetos referenciados.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Capturar delete completo

Guardar una secundaria completa en fixture, abrir diálogo de borrado y registrar solicitud/ACK/lock. Revisar cnO ycnP/cEN para longitudes/campos y estatus.12837 corresponde a deletion, no activación; no intercambiar contratos.

## 2. Validar índice y referencias

Comprobar ownership/lease, existencia, permiso de fase y protección de build 0. Definir fallback si se borra activa; equipo de una hoja son referencias a inventario, no propiedad exclusiva: eliminar hoja no destruye unidades.

## 3. Confirmar eliminación y selección

En una transición quitar las cuatro hojas del índice, actualizar selección/revisión y recomputar estado si aplica. Journal debe reflejar tombstone/remoción y no resucitarlo durante flush o baseline conflict. Retry de índice ya eliminado devuelve resultado idempotente definido.

## 4. Responder y desbloquear

Enviar carrier 12837 probado y updates de colecciones/selección; restaurar heroBuildLock en success/reject. Los peers no necesitan inventario privado. Bootstrap posterior no anuncia el índice eliminado por un default sintético.

## 5. Validar lifecycle

Delete activa/inactiva, intento de 0, combate, retry, sesión sustituida y recovery. Añadir prueba gráfica del diálogo y permisos; una ausencia de handler está confirmada por código, el bloqueo visual aún necesita captura.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Eliminar una hoja no elimina sus objetos; selección válida y controles se restauran en todas las salidas.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
