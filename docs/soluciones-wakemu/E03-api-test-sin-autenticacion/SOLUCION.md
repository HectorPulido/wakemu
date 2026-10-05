# Solución propuesta — E03

Autenticar y autorizar todas las rutas de prueba y tareas, conservando separación de roles.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Auditar orden de dispatch HTTP

Enumerar paths/métodos/límites del body y en qué momento se evalúan tokens. Dibujar matriz de acceso a comandos, tareas y resultados y endpoints de juego. No limitar revisión al POST si GET de handle expone resultados sensibles.

## 2. Definir principales y permisos

Cuenta de administrador puede ejecutar comandos según 32; principal del cron solo tareas explícitas. Tokens necesitan scope/expiry/revocación y propiedad del objetivo. Bearer de usuario normal no permite elegir otro ID de personaje ni usar task arbitraria.

## 3. Autorizar antes de encolar

Parsear/auth/rate/rol/lease del objetivo primero y crear el handle después. En el job revalidar lease y revocación según política. Anónimo no obtiene handle ni consume cola; body/request_id falsificado no elude checks.

## 4. Proteger callbacks y resultados

Cada handle ligado a solicitante/operación; GET requiere permiso. Tasks whitelist/principal/lease/idempotencia impiden ejecutar callback arbitrario. Reintento autorizado resuelve recibo; token distinto no lee job de otra cuenta.

## 5. Probar API y exposición

HTTP401/403/400 consistentes, ninguna mutación o secreto en logs. Ensayar localhost y remotos controlados tras permisos; el bind se configura por separado. Mantener arranque de herramientas de prueba compatible con autenticación propia sin una excepción anónima oculta.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Ningún endpoint de prueba elude autenticación por estar antes de la rama común.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.

## Evidencia adicional ejecutada

[Cotejo posterior a las respuestas del usuario](REVISION-RESPUESTAS.md).
