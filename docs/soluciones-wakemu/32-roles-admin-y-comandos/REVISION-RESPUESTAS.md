# Roles y comandos: autorización en todas las entradas

## Reproducción actual

API actual ejecutada en puerto efímero localhost con Store/cola ficticios: POST sin Authorization a **/test/command** y **/test/tasks/audit** devuelve202 y encola; `store.token` se llamó **0 veces**. No hubo DB ni comando real. [Resultados y hash](probe-api-sin-autorizacion-actual.json). Revalida E03 en la versión actual, no demuestra alcance de red externo.

En chat12366 el flag global `WAKFU_TEST_CONSOLE` habilita `execute_test_command`, con default1; tampoco consulta rol. En drenaje de LiveConsole se verifica generación/hilo, pero no identidad del solicitante ni permiso actualizado. Validar lease del personaje dentro del comando no autentica al llamante HTTP.

## Política respondida

Admin puede ejecutar comandos registrados `!`; jugador solo allowlist configurable DB. «Todos» no significa permitir nombres desconocidos o argumentos inválidos: mantener parser/guardas y ownership. Rol de cuenta defaultjugador, concesión/revocación por canal administrativo autorizado; no dejarlo seleccionable en register.

## Integración concreta

Crear autoridad central `authorize_command(principal,command,target,context)` llamada **antes de encolar y antes de ejecutar**, compartida por chat/API/tasks. Canonicalizar nombre como hace test_console (`split()[0].lower()`), validar contra registro real y consultar allowlist DB versionada. Propuesta de baseline jugador: conjunto vacío hasta configuración explícita; !ayuda/!pos pueden habilitarse individualmente. No usar prefijos ni substring que habiliten !item por coincidencia.

Autenticar Bearer antes de acceder a /test/command y /test/tasks; 401 sin principal válido,403 principal autenticado sin permiso. Target debe pertenecer al alcance autorizado: jugador solo su personaje activo; facultad admin sobre otro personaje debe ser permiso explícito. Registrar principal/cuenta destino/generación/nombre comando/policy_revision en recibo; `request_id` debe incluir principal en su clave, no solo personaje/generación.

Drenar reconsulta rol/policy y rechaza revocados **antes de flush_positions o cualquier mutación**. Una autorización guardada al encolar no sigue siendo válida tras revoke. Token de cron/principal servicio solo tareas predefinidas autorizadas, nunca todos los comandos. GET sesiones/resultados necesita auth y filtro por principal; conocer handle no concede permiso. Retener auditoría sin secretos y limitar cola por principal.

## Límites

No se implementaron roles/política,401/403 ni revocación; la prueba actual valida bypass, no su corrección. Faltan pruebas de admin/jugador/cron, targets ajenos, comandos equivalentes por mayúsculas, revocación entre enqueue/drain y acceso a resultados. Mantener el interruptor global como barrera adicional; no sustituye roles.
