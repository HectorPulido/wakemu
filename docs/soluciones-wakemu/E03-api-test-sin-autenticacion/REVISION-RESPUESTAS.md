# Verificación HTTP ejecutada

Se arrancó un servidor HTTP efímero exclusivo en localhost con callbacks simulados, sin llamadas al servidor real. [Resultados de siete casos](probe-auth-http.json).

POST `/test/command` sin credencial **y con credencial inválida** devolvió 202 y ejecutó el callback sin evaluar autenticación. POST `/test/tasks/positions_flush` devolvió 200 y ejecutó el callback global sin token. GET `/test/sessions`, `/test/command/synthetic-handle` y `/test/tasks` devolvieron 200 sin comprobación de token. Como control negativo, GET `/characters` devolvió 401 y sí invocó la validación.

El código explica el resultado: las ramas `/test/*` están antes de la rama común `store.token`, tanto en POST como en GET. No es solo ausencia de un test: hay bypass reproducido del control HTTP. El alcance depende de los callbacks habilitados y del bind efectivo; localhost no sustituye autorización de comandos.

La corrección propuesta es autenticar y autorizar **antes** de enviar a console/tasks o devolver resultados, usando el rol administrador y allowlist configurable de jugadores del issue 32. Revalidar identidad de personaje y sesión al ejecutar. No otorgar capacidades por llamar a la ruta «test». Los casos futuros deben afirmar ausencia de callback/handle para 401/403, no solamente el status HTTP. No se implementó el cambio.
