# Issue 21 — Configuración de conexión, alcance servidor

## Respuesta y alcance

El usuario respondió «Revisa todo. Nada que decidir» y posteriormente limitó mejoras al servidor. La petición inicial de `.env` para tools se conserva como contexto, pero no autoriza modificar cliente/tools dentro de esta auditoría. No se necesita otra decisión para cotejar endpoints del servidor.

## Configuración actual cotejada

`local_game_server.realms_local` reemplaza el endpoint del realm10 por `WAKFU_ADVERTISE_HOST` y `WAKFU_ADVERTISE_WORLD_PORT`. Solo acepta IPv4 literal mediante `ipaddress.IPv4Address`; no acepta hostname ni IPv6. Rechaza dirección unspecified/multicast y puertos fuera de1–65535. El default anunciado es **127.0.0.1:15556**.

El listener usa `WAKFU_BIND_HOST`, default127.0.0.1. Dockerfile lo establece **0.0.0.0** dentro del contenedor, pero Compose publica mundo15556, dispatcher15558 y API18081 exclusivamente sobre **127.0.0.1 del host**. Cambiar el host anunciado no cambia esa publicación ni vuelve accesible el servidor remoto por sí solo. Un cliente remoto que recibe127.0.0.1 intenta conectar a su propio equipo, salvo túnel local correspondiente.

Los logs/print del listener anuncian siempre127.0.0.1 aunque bind use otro valor: no son evidencia fiable de la interfaz real. Verificar sockets efectivos y publicación Compose. El API usa el mismo bind host del proceso; no exponerlo al habilitar juego remoto sin revisar autenticación/roles (issue32).

## Solución concreta del servidor

Mantener separados bind interno, endpoint anunciado y publicación externa. Validarlos al arrancar, registrar valores efectivos sin secretos y comprobar que el realm anuncia el puerto público correcto aunque el contenedor use otro. Direcciones y credenciales son configuración de despliegue; las reglas de juego migran a DB según el requisito transversal.

Para remoto, publicar o tunelizar específicamente los puertos de juego necesarios y anunciar una IPv4 accesible coherente con esa topología. No anunciar0.0.0.0, que es dirección de escucha. No modificar automáticamente cliente, firewall ni DNS en esta auditoría. Si se amplía soporte a hostname/IPv6, primero cotejar consumidor nativo de realm y transporte; no eliminar la validación sin probar el contrato.

Corregir observabilidad para registrar bind real y endpoint anunciado por separado. Probar arranque con valores inválidos antes de abrir sockets. Evitar que API administrativa/test y Redis queden publicados por compartir una decisión de bind; conservar listeners/permisos independientes.

## Verificación restante

No se realizó conexión desde otro equipo ni se cambió Compose. Falta fixture nativa del anuncio de realm y prueba autenticada a través de publicación/túnel propios. El código confirma incompatibilidad del defaultlocalhost con conexión remota directa; no demuestra un fallo específico en la red del usuario. No se aplicaron fixes ni cambios al cliente.

## Prueba del anuncio actual: ocho configuraciones

[Probe ejecutado](probe-anuncio-endpoint.json): se extrajeron por AST solo `pack_text` y `realms_local` del código actual, sin importar el módulo que arranca dependencias. Una fixture mínima de realm10 conservó su identidad/nombre y publicó correctamente localhost15556 y dirección de documentación **192.0.2.50:25556**. Rechazó hostname, IPv6, unspecified, multicast y puertos0/65536. Esta prueba no abre sockets ni demuestra conectividad de192.0.2.50, dirección reservada para ejemplos.

La fixture verifica el encoder Python y lectura de campos, no el consumidor Java del realm. El parser actual conserva metadatos del template y exige un realm/config10; falta probar fixtures con realm ausente/duplicado y errores recuperables, además de conexión real. Los asserts actuales no equivalen a validación de despliegue con diagnóstico explícito.
