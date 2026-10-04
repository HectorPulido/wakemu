# Experimento local de Wakfu

## Carpetas

- `client/`: carpeta excluida íntegramente de Git. Cada usuario debe aportar su propia copia del cliente y sus assets; este repositorio no los distribuye.
- `sniffer/`: captura y decodificación. `java/` contiene los agentes y exportadores; `tools/`, las comparaciones externas.
- `server/`: servidor Python, servicio de IA, catálogos del protocolo, pruebas y Dockerfile.
- `docs/`: documentación, informes y evidencia del protocolo. El historial completo está en `docs/reports/progress.txt`.
- `.runtime/`: datos privados y generados: SQLite, certificados, perfiles, registros y capturas. Se conserva fuera de código y documentación.

## Requisitos y archivos externos

Coloca tu propia copia del cliente en `client/`. Ningún archivo de esa carpeta, incluidas las herramientas locales, se distribuye en este repositorio. Los comandos de cliente siguientes describen el entorno original y requieren que esas herramientas estén disponibles por separado.

Compose también requiere la captura externa indicada en su volumen `/fixtures/frames.jsonl`; `.runtime/` no se distribuye. El informe grande `docs/reports/combat-inventory/inventory.json` se incluye comprimido como `inventory.json.gz`.

## Arranque local

Desde esta carpeta:

```bash
docker compose up -d --build
docker compose ps
bash client/tools/local-client.sh
```

Para abrir otra instancia: `bash client/tools/local-client.sh --profile nombre`.

```bash
docker compose logs -f world
PYTHONPATH=server python3 -m unittest discover -s server/tests
```

La base de datos existente permanece en `.runtime/local/world.sqlite3`. Los eventos detallados están en `.runtime/local/logs/game-server.jsonl`.

## Organización del servidor

`server/local_game_server.py` conecta el protocolo con los servicios. Los módulos están en `server/wakfu_server/`:

- `combat/`: turnos, movimiento, ataques, IA, muerte y recompensas.
- `items/`: inventario, bolsas, equipamiento, builds y merkasacos.
- `maps/`: jugadores en el mundo, desplazamiento, transportes y objetos.
- `storage/`: SQLite, posiciones en memoria y Redis.
- `characters/`: creación, vida, experiencia, hechizos y datos sociales.

`server/ai-service/` es un proceso HTTP independiente. Compose mantiene IA y Redis en una red interna; el servidor publica los puertos del cliente solo en localhost.

El objetivo completo del emulador sigue en desarrollo. La separación de carpetas no implica que todos los sistemas del juego estén implementados.
