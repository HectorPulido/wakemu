# Diagnóstico — 21

## Contexto registrado

**Confirmado:** scripts locales fijan `127.0.0.1`; el launcher portable ya admite host y puertos mediante JSON y variables concretas, pero no se encontró un cargador común `.env`. `portable_config.py` restringe el host a IPv4 numérica y el guard de red forma parte del arranque.

**Posible solución:** cargador único para host, API y puertos, con ejemplo versionable sin secretos, usado también al generar configuración y permiso de red. `127.0.0.1` apunta al equipo del usuario, no al remoto, salvo un túnel local. Mantener el inspector local separado de la dirección del juego. **Validación:** valores por defecto, IP remota, configuración inválida y todos los endpoints coherentes.

**Distribución:** `/client` está íntegramente excluido de Git por instrucción del usuario. Las herramientas propias redistribuibles deberán residir fuera de esa carpeta, sin incorporar binarios/assets del cliente.

Extra: igual permitir al servidor recibir request desde la red externa 0.0.0.0

## Lectura actual

El host por defecto es localhost. Separar bind y dirección anunciada y revisar autenticación de rutas de prueba antes de exponer. Cambiar tools del cliente queda fuera del alcance solicitado.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Host/IP remoto, puertos necesarios, TLS/túnel y firewall.
- Prioridad actual del pedido.env de tools versus restricción de cambios solo server.
- Política de exposición de API/test/admin y evidencia de auth.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
