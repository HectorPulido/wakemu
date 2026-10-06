# Implementación y verificación — 2026-10-05

Este registro conserva los pasos del despliegue inicial, cuando el backend aún usaba SQLite. Esa operación y su `HEAD` son históricos; no describen el almacenamiento activo posterior a la migración PostgreSQL.

Autorizada por el usuario la implementación, modificación de DB y reinicio de Docker. Checkout Wakemu local `main`, HEAD base `6a9ce6e3bbdd6d27f4142a148f4f58824386c126`, cambios sin commit ni push. No se modificó Dofus/Starloco. El checkout tiene cambios de otra sesión, por lo que HEAD no identifica todo el código desplegado.

## Comportamiento implementado

- `accounts.is_admin` inicia en0; no se elevan cuentas existentes ni se acepta un rol en registro/login. Cambio offline mediante `server/tools/manage_permissions.py role`, con operador/motivo y auditoría durable.
- Política configurable en DB `settings.player_allowed_commands`, JSON de nombres. Default `!ayuda` y `!pos`; admins pueden solicitar todos los comandos existentes, manteniendo validaciones de argumentos, propiedad y lease. Política inválida falla cerrada.
- Chat consulta permisos antes de flush/mutaciones, y el helper comprueba de nuevo. Rechazos por permisos se notifican sin cerrar la sesión.
- Todas las rutas `/test/*` necesitan Bearer válido. Token inválido/expirado/revocado:401; cuenta normal o scope inválido:403. La API de consola queda restringida a administradores sobre sus propios personajes; los jugadores usan únicamente comandos permitidos por chat.
- Jobs ligados al solicitante; lectura de resultados y sesiones aislada por cuenta. Se revalidan token, rol y propiedad al ejecutar jobs encolados; revocación impide callbacks.
- Principal `scheduler` con token revocable/expirable, limitado a los callbacks globales registrados: positions/builds/groups flush. No puede ejecutar comandos, listar sesiones ni leer resultados. La cuenta técnica no es admin.
- Cron autentica POST y polling; credencial en archivo privado0600 montado read-only. El archivo no se publica. La credencial desplegada caduca en un año; rotar antes de vencimiento y revocar la anterior con `Store.revoke_token`. El helper permite TTL explícito y evita sobrescribir archivos existentes.

## Evidencia

`PYTHONPATH=server python3 -m unittest server.tests.test_store server.tests.test_command_permissions server.tests.test_chat_console server.tests.test_live_console server.tests.test_global_tasks server.tests.test_api_authorization -q`: **29 tests OK**.

Matriz HTTP efímera: anónimo/inválido/jugador contra seis rutas, sin callbacks ni handles; admins, personaje ajeno, resultados ajenos, revocación de rol/token con job pendiente; scheduler permitido/rechazado; JSON inválido y salud pública.

En esa validación inicial, la base SQLite se comprobó desde Docker con `PRAGMA quick_check`:ok y se guardó el backup `.runtime/local/backups/before-command-permissions-20261005.sqlite3` antes de cambiar roles. No se elevó ninguna cuenta del usuario; se creó una cuenta técnica sin personaje para cron.

En aquel despliegue se reinició `world` y se recreó `cron`. El smoke inicial observó `/health`200; anónimos `/test/sessions`, `/test/tasks`, `/test/command/invalid`401; scheduler `/test/tasks`200, `/test/sessions`403 y POST `positions_flush`200/completed. No se imprimieron tokens.

## Revalidación del backend PostgreSQL — 2026-10-05

Con el backend migrado, se volvieron a ejecutar las suites de API, permisos, chat y tareas contra PostgreSQL con migraciones 001–008. Resultado: **20 tests OK**. Ver matriz, comando y alcance en [PRUEBAS.md](PRUEBAS.md). Cada caso usa un esquema aislado; las cuentas admin de prueba son efímeras y no modifican roles de usuarios reales. El estado operativo actual debe obtenerse del entorno, no inferirse de la sección histórica SQLite anterior.

## Estado y límites

E03: bypass de autenticación corregido y probado, incluidos tareas, resultados y revocación de jobs.32: control de rol/configuración implementado y probado en backend; falta comprobar rechazo y continuidad de sesión desde chat de una partida real. Ninguna prueba HTTP equivale a ese recorrido gráfico. No se han resuelto los demás issues por cambiar esta barrera.

## Operación

En el entorno que accede a la DB, con `PYTHONPATH=server`: `python3 server/tools/manage_permissions.py --database RUTA role --account-id ID --admin yes --operator OPERADOR --reason MOTIVO`. Revocar con `--admin no`. No otorgar rol por nombre del personaje ni por primer login. El CLI es una herramienta offline de operador, no un endpoint accesible a jugadores.

Para emitir credencial de cron: subcomando `scheduler-token --account-id ID --output ARCHIVO_PRIVADO --ttl-seconds TTL`. Configuración del cron `WAKFU_CRON_API_TOKEN_FILE`; alternativamente `WAKFU_CRON_API_TOKEN` fuera del repositorio. El token es infraestructura/credencial, no un parámetro de balance en DB.
