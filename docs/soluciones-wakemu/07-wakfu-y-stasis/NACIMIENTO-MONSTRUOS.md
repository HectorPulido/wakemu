# Progreso personal al nacer un monstruo sembrado

## Flujo actual comprobado

`Plantings.complete` confirma una semilla en etapa1; todavía no existe un monstruo y no se concede progreso personal. `Plantings.mature` confirma outbox y retirada de la semilla juntos. Después, `publish_growth` llama `PersistentGroups.register`, que confirma grupo y membresías en otra transacción, publica12782/12608 y marca el outbox después del envío.

Un fallo de publicación conserva el evento para reintentar. Sin embargo, esta separación impide añadir simplemente un premio en `mature`: el grupo todavía no forma parte del conteo SQL y varios nacimientos pendientes podrían clasificarse contra el mismo conteo.

## Cambio necesario

1. Persistir la atribución al personaje mediante una columna indexada de UID de recurso en el recibo de plantación; validar unicidad y coherencia con su JSON.
2. Extraer la escritura de grupo/membresías a una operación que acepte la conexión/transacción del llamador. Mantener validación nativa, identidad, revisión y rechazo de rosters contradictorios.
3. Tomar primero el bloqueo del personaje atribuido y después el evento pendiente; la semilla ya fue retirada, por lo que no se espera una fila de recurso manteniendo el personaje bloqueado. Confirmar activación del grupo y recibo personal `monster-birth:<resource_uid>` en una transacción. Clasificar el conteo anterior por región nativa y familia de la referencia efectivamente nacida; no contar semillas como animales.
4. Serializar escritores de población: reproducción, nacimiento, cambio de familia por maduración y desplazamiento entre regiones. El bloqueo Python del proceso no cubre otros trabajadores. Revisar un orden común de bloqueos SQL antes de integrar: las acciones personales bloquean primero el personaje, por lo que bloquearlo después de recurso/población puede invertir el orden.
5. Publicar tras commit y confirmar outbox solo después del envío. El replay no vuelve a tirar ni concede otro premio. Restaurar el valor absoluto al reconectar; si el dueño está conectado en otra zona, enviar a su sesión actual, no exclusivamente al mapa del nacimiento.

## Casos obligatorios de verificación

Nacimiento con dueño conectado/desconectado; dueño que cambia de zona; superficie desconocida sin premio inventado; fallo SQL de grupo/membresía/recibo con rollback; dos nacimientos simultáneos al límite; fallo de socket y reinicio antes/después del commit; un solo crédito por UID; grupos pendientes anteriores sin premio retroactivo accidental.

Esto describe trabajo pendiente, no una garantía implementada. No requiere modificar hechizos ni ejecución de combate.

## Preparación implementada, sin desplegar

`PersistentGroups.register_transaction` acepta una transacción activa del llamador y conserva las validaciones de roster y membresías. `register` abre su transacción y delega. Gate31 PostgreSQL/Redis aprobado, incluidos cuatro casos específicos de transacción requerida, rollback del llamador, conflicto de membresía e idempotencia sin commit propio.

Migración028 añade `planting_receipts.resource_uid` generado del JSON, positivo para éxitos, nulo para fallos y único. Evita divergencias entre dos campos editables. Preflight de la base activa:15 recibos,7 éxitos, cero UID ausentes/no positivos y cero duplicados. La migración todavía no está aplicada. Gate99 PostgreSQL aislado aprobado: identidad generada/única, rechazos, atribución después de retirar planta y aplicación a recibos poblados de migraciones1–27. Esto no implementa aún el premio del nacimiento.

## Activación ecológica en fuente

`monster_birth_ecology.activate` bloquea personaje atribuido, evento pendiente y población de monstruos, en ese orden. Registra grupo y recibo personal en la transacción del llamador; el replay devuelve el valor personal actual sin otro premio. Un grupo activado por código anterior no recibe crédito retroactivo. Sin atribución o población/superficie verificable, conserva el nacimiento sin inventar progreso. El evento sigue pendiente de publicación después del commit.

Todavía no está conectado a `publish_growth` ni desplegado. Sus pruebas dirigidas están delegadas; falta integrar entrega al dueño que cambió de zona y serialización de todos los escritores regionales.

## Integración y gate dirigido

Activación conectada a `Plantings.publish_growth`; el callback del servidor carga el valor confirmado y `World.publish_ecology` actualiza únicamente los campos ecológicos de la sesión actual, preservando ubicación y rechazando revisiones antiguas. El dueño offline restaura mediante bootstrap. Gate61 PostgreSQL aislado aprobado en nacimiento/runtime/world: rollback, concurrencia entre cuentas, reintentos con roster actual y grupos luchando/derrotados sin reaparición.

El orden poblacional se amplió en fuente: registro de grupos, movimiento, maduración y reproducción toman el advisory de población antes de bloquear/mutar grupos. Gate ampliado93 PostgreSQL/Redis aprobado, incluida carrera entre nacimiento y cambio de región con conteo/delta coherentes. La atribución por victoria/retirada de combate sigue pendiente y no se modificó ejecución ni hechizos. Todavía sin despliegue de esta integración.
