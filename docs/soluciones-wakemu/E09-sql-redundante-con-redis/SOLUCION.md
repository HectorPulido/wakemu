# Solución propuesta — E09

Separar migraciones/hidratación del camino caliente y evitar SQL completo después de un hit válido.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Trazar por operación

Repetir sql-redis-probe con hash actual y registrar statements/tipos, no solo tiempo total. Diferenciar CREATE/INSERTORIGNORE de filas nuevas; no decir que cada carga duplica objetos. Medir también cambios de memoria/CPU y bytes de snapshot.

## 2. Mover schema e inicialización

Aplicar migration al arrancar de manera controlada y seed idempotente al crear personaje, no cada load. Las validaciones de integridad/ownership permanecen en reads necesarios. Si schema ausente, fallar con mensaje claro, no recrearlo sin límite en cada solicitud.

## 3. Definir snapshot cacheado completo

Clave cuenta/personaje con schema/version/revisión y dominios incluidos. Hit válido devuelve estado sin SELECT de cada tabla; miss real carga y publica atómicamente. Leases y datos sensibles tienen autoridad/revocación separadas; no cachear permisos para siempre.

## 4. Invalidar y coordinar writers

Todo writer de inventario/progreso/salud/merkasaco debe actualizar o invalidar versión. Un snapshot deSQL sin mutación Redis pendiente no puede reemplazar el actual. Consultar parte SQL por salud no obliga a recargar todas las hojas; documentar lecturas inevitables por dominio.

## 5. Comparar costo y corrección

Casos hit/miss, mutation concurrente, schema antiguo, recovery y Caída de Redis. Repetir con Redis real bajo carga antes deatribuir mejora de latencia; la fixture subms solo prueba diseño. Mantener usuario 0 flush 20 minutos y garantías de recibos.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Una cache válida reduce SQL sin perder ownership, revocación o mutaciones pendientes.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
