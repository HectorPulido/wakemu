# Reglas de implementación y verificación

## Criterio de arquitectura autorizado — 2026-10-05

El usuario prioriza código limpio y escalable sobre retrocompatibilidad. Se autorizan cambios incompatibles de esquema, API interna y formatos persistidos, incluso si la base anterior deja de funcionar. No mantener lectores legacy, traductores de SQL SQLite, doble backend, dual-write ni fallbacks para preservar contratos abandonados. Reescribir callers y pruebas alrededor del contrato definitivo.

Un backup/exportación puntual es recuperación operativa, no una obligación de restaurar compatibilidad. Conservar datos antiguos solo si aporta valor sin condicionar el diseño; se permite empezar con una base nueva. Mantener los contratos nativos que necesita el cliente de juego: esa interoperabilidad sigue siendo requisito funcional, no retrocompatibilidad de nuestra implementación.


## Autoridad y alcance

Trabajar solo en el servidor y sobre un entorno autorizado. No editar el cliente para ocultar un defecto de estado o protocolo. Separar código del checkout, snapshot del ensayo y versión desplegada; registrar identidad de instancia y versión real. Los cambios concurrentes obligan a repetir el cotejo de archivos afectados.

## Transacciones y recibos

Validar formato, ownership, lease/generación, fase y revisión antes de mutar. Una operación de valor debe confirmar cambios y recibo en la misma autoridad durable. El recibo permite devolver el resultado anterior ante reintento, no volver a aplicar consumo/concesión. Los UID no se reutilizan ni cambian propietario mediante una actualización parcial insegura. Transferencias bilaterales necesitan confirmar ambos lados juntos.

## Redis primero y flush de 20 minutos

Definir por dominio qué almacén es autoritativo. Un journal de builds no es automáticamente una cache completa del personaje. Verificar configuración efectiva de Redis y garantías de durabilidad; no aceptar un ACK de memoria como prueba frente a caída del host. Ante error Redis con mutaciones pendientes, no hacer fallback a SQL antiguo.

Guardar lotes SQL por revisión y limpiar journal solo si esa revisión continúa vigente. Un corte después de commit y antes de limpiar se recupera sin concesións duplicados. Una revisión nueva nunca se elimina por el flush de una anterior. El requisito de 1.200 segundos necesita políticas explícitas para salud, leases y operaciones de valor actualmente inmediatas; no cambiar todos los temporizadores a ciegas.

## Protocolo y concurrencia

Distinguir petición, ACK, delta y snapshot completo. Usar fixtures mínimas y decodificadores de referencia para campos, longitudes, signedness y estados de error. Un modelo visual optimista no prueba commit. Snapshot y eventos deben compartir revisión/secuencia, con colas acotadas; evitar enviar a sockets lentos manteniendo locks globales.

## Recuperación y entrega

Ensayar antes de commit, después de commit y antes del ACK. Probar sesión revocada, replay, reconnect y observers cuando corresponda. Validar el esquema nuevo, las transacciones y sus consumidores sin exigir lectores antiguos. Si se importa información anterior, probar la importación sobre una copia consistente y documentar los registros rechazados; comenzar con una base vacía también es válido. No recuperar mediante SQL antiguo si existen mutaciones posteriores confirmadas.

No publicar bases, tokens, capturas privadas, logs personales ni archivos propietarios del cliente. No se autoriza reinicio, commit, push o despliegue por la existencia de estos planes. Registrar PASS/FAIL/NO EJECUTADO y no confundir tests de base con aceptación de una solución aún no implementada.
