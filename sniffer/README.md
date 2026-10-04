# Captura y análisis

Ejecutar desde la raíz del proyecto:

```bash
bash sniffer/build-capture-agent.sh
bash sniffer/decode-session.sh .runtime/captures/ID_DE_CAPTURA
python3 sniffer/audit-capture.py --help
```

Las capturas permanecen en `.runtime/` porque contienen datos privados y algunas son fixtures necesarias para arrancar el servidor. Los exportadores Java leen el cliente instalado en `client/` y generan catálogos en `server/protocol/`. No realizan peticiones al juego.

Los scripts de autenticación y captura del launcher son herramientas históricas: no ejecutarlos como parte del arranque del servidor local.
