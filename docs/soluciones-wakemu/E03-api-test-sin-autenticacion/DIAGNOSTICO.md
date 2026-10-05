# Diagnóstico — E03

## Contexto registrado

api.py maneja/test/command y tareas antes de validar bearer en la rama común. Ownership deltarget o acceso localhost no equivalen a autenticación del solicitante. Exponer0.0.0.0 sincerrar esta ruta aumenta alcance deldefecto.

## Lectura actual

POST procesa tareas y comandos antes de store.token; GET también devuelve sesiones y resultados antes de auth. Reordenar guardas y añadir autorización de función/target antes de cualquier efecto.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Scopes/tokenservicio y contrato HTTP decididos.
- Política de admins actuando sobre otros personajes.
- Todos los endpoints detasks/resultados y exposiciónreal.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
