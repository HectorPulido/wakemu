# Diagnóstico — 32

## Contexto registrado

**Confirmado:** el esquema de `storage/store.py` no contiene `is_admin` en cuentas. El handler `12366` de `local_game_server.py` ejecuta comandos `!` cuando `WAKFU_TEST_CONSOLE=1`, sin comprobar un rol por cuenta. Ese flag es global y no equivale a autorización individual. `maps/test_console.py` valida propiedad/lease de personaje y argumentos, pero tampoco rol administrativo.

**Hallazgo relacionado:** `api.py` atiende `/test/command` y algunas tareas `/test/tasks/` antes de la rama que valida el token API. Proteger solo el chat dejaría una ruta alternativa para ejecutar comandos por ID de personaje cuando la consola está habilitada. Es relevante antes de habilitar acceso externo, como solicita el ítem 21; no se cambió ninguna exposición de red.

**Posible solución del servidor:** migración de cuentas con `is_admin NOT NULL DEFAULT 0`, sin convertir automáticamente en administradores las cuentas existentes ni permitir elegir el rol al registrarse. Usar una comprobación central en todos los accesos a comandos, autenticando al solicitante también en API; distinguir comandos informativos de comandos que alteran datos si se define esa política. El rol se concede mediante operación administrativa explícita y debe poder revocarse durante una sesión. Mantener el flag global como interruptor adicional, no como sustituto del permiso.

**Validación:** cuenta normal rechazada por chat y API sin mutaciones; admin autorizado; petición anónima rechazada; revocación efectiva; intentos contra otro personaje y tareas predefinidas; registro de actor, comando y resultado sin credenciales.

## Lectura actual

Las ramas /test/command y /test/tasks se ejecutan antes de la validación Bearer común. Roles de admin y ownership deben validarse tanto en API como en ejecución de consola; localhost no reemplaza autorización.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Política exacta de comandos públicos versus restringidos.
- Mecanismo autorizado de concesión/revoke y principal del cron.
- Contrato HTTP401/403 y revalidación de jobs ya encolados.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
