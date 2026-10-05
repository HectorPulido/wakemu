# Solución propuesta — 32

Autorizar comandos por cuenta y cerrar rutas alternativas antes de exponer el servidor.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Inventariar accesos a comandos

Listar chat 12366, API/testcommand, tasks y helpers directos. WAKFU_TEST_CONSOLE es interruptor global, no rol. Lease/ownership garantizan personaje pero no privilegio; no confundir esos checks con permiso administrativo.

## 2. Migrar rol sin elevación accidental

Proponer is_admin NOTNULLDEFAULT0 con concesións auditables explícitos; registro/login no aceptan rol del usuario. Identificar mecanismo autorizado para otorgar/revocar rol y auditar actor/operación. No elevar cuentas existentes por username o primer login.

## 3. Centralizar autorización

Una función authenticate+authorize por operación evalúa rol vigente y consola global. Definir si !help/!pos son públicos o todos! restringidos; mantener política uniforme chat/API. Al recibir request comprobar antes de cola/mutación, no después de ejecutar.

## 4. Cerrar bypass de API y tasks

E03 exige token para/testcommand y privilegio para tareas; verificar ownership y lease del target. Un request_id/idempotency no concede permiso. Para cron usar principal servicio limitado a tasks de flush, no token admin de jugador difundido a terceros.

## 5. Revocar durante sesión

Rol no se cachea indefinidamente: revisión/invalidation o consulta autoritativa. Si admin se revoca, comandos en cola se revalidan según política; sesión reemplazada no sigue mutando. Registrar rechazo sin contraseña/token/payload sensible.

## 6. Validar matriz de autorización

Chat y API por normal/admin/anónimo/revocado, consolaon/off, target propio/ajeno y formatos inválidos. La prueba no debe crear admins reales ni tocar cuentas del usuario; usar DBtemporal y asserts de ausencia de mutaciones.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Autenticación, rol, ownership y lease se comprueban separadamente antes de cualquier mutación.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
