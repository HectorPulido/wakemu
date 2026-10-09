# 21. Tools con configuración `.env` del servidor

Documentar contrato de endpoints y acceso externo del servidor; conservar fuera de scope cualquier cambio de cliente.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**🟡 Solucionado parcialmente.** La configuración de red del servidor y su verificador están implementados en fuente. La conexión desde otro equipo sigue pendiente; las pruebas locales no acreditan acceso remoto.

## Dependencias

32 y E03 antes de exposición externa. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Bind y anuncio son distintos; acceso de red nunca reemplaza autenticación ni autoriza publicar assets del cliente.

## Avance — 7 de octubre

**Solucionado parcialmente.** Se añadió `.env.example` y `server/tools/check_server_network.py`; distingue bind/anuncio, valida IPv4/puerto, respeta precedencia del entorno y no imprime secretos. Compose permite WAKFU_BIND_HOST conservando0.0.0.0 como default interno y publicaciones localhost. Tres pruebas de configuración pasaron (incluidos comentarios tras valores entre comillas) y `docker compose config --quiet` aprobó. No hay exposición remota ni cambios de cliente; la conexión desde otro equipo sigue pendiente.


Implementación remota directa en fuente: [guía de servidor y cliente](../../reports/wakemu-remote-client.md), override compose opt-in, IP/puertos explícitos y proxy HTTPS limitado a login/remember/game-token. API completa permanece en loopback y DB/Redis no se publican. Validación:2 pruebas de configuración, render Compose, nginx efímero sin puertos publicados con handshakeTLS y rechazo404/403. Falta conectar desde otro equipo con IP/certificado reales y acreditar upstream de autenticación. No instalada ni exposición remota habilitada.
