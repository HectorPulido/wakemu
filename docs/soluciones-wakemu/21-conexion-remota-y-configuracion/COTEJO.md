# Cotejo de código — 21

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**El host por defecto es localhost. Separar bind y dirección anunciada y revisar autenticación de rutas de prueba antes de exponer. Cambiar tools del cliente queda fuera del alcance solicitado.**

Función `serve_api`, línea 6 de [server/wakfu_server/api.py](../../../server/wakfu_server/api.py). SHA-256: `b387ef1a986bf44f5bf65ab903dd7934fff15cb10b0c0d53b313af27143a890e`.

```python
def serve_api(
    store,
    host="127.0.0.1",
    port=18081,
    *,
    live_console=None,
    on_ready=None,
    test_tasks=None,
    global_tasks=None
):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log passwords, authorization headers or tokens.

        def reply(self, status, value):
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 8192:
                    raise ValueError("Petición inválida.")
                body = json.loads(self.rfile.read(length))
                if self.path.startswith("/test/tasks/") and global_tasks is not None:
                    name = self.path.rsplit("/", 1)[1]
                    if name in global_tasks.names():
                        return self.reply(
                            200, global_tasks.run(name, body.get("request_id"))
                        )
                if (
                    self.path.startswith("/test/tasks/")
                    and test_tasks is not None
# Fragmento truncado; consultar la función completa en el enlace.
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [compose.yaml](../../../compose.yaml) | c56c61058637 | Configuración; revisar valores y uso por el proceso. |
| [server/local_game_server.py](../../../server/local_game_server.py) | edbb31c2577a | `known_transports` L99, `position_lease_active` L114, `flush_positions` L128, `flush_position_batches` L144, `pack_text` L210, `realms_local` L215, `fixture` L269, `character_list_local` L282, `player_template` L293, `write_records` L322 |
| [server/wakfu_server/api.py](../../../server/wakfu_server/api.py) | b387ef1a986b | `serve_api` L6, `log_message` L17, `reply` L20, `do_POST` L29, `do_GET` L120 |
| [server/wakfu_server/profiles.py](../../../server/wakfu_server/profiles.py) | 767997fcee13 | `profile_root` L9 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Separar bind de dirección anunciada | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Definir contrato de configuración | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Corregir superficie de autorización primero | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Preparar exposición revisable | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Verificar desde dos ubicaciones | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
