# Experimento local de Wakfu

## Carpetas

- `client/`: carpeta excluida íntegramente de Git. Cada usuario debe aportar su propia copia del cliente y sus assets; este repositorio no los distribuye.
- `client-tools/`: herramientas propias de lanzamiento, autenticación, diagnóstico y parches; usan el cliente de la carpeta hermana `client/`.
- `sniffer/`: captura y decodificación. `java/` contiene los agentes y exportadores; `tools/`, las comparaciones externas.
- `server/`: servidor Python, servicio de IA, catálogos del protocolo, pruebas y Dockerfile.
- `docs/`: documentación, informes y evidencia del protocolo. El historial completo está en `docs/reports/progress.txt`.
- `.runtime/`: datos privados y generados: SQLite, certificados, perfiles, registros y capturas. Se conserva fuera de código y documentación.

## Requisitos y archivos externos

Prepara las carpetas y credenciales privadas con `python3 tools/prepare-local-runtime.py`. No reemplaza secretos existentes. El [informe de portabilidad](docs/reports/runtime-portability-audit.md) detalla las dependencias privadas que todavía impiden arrancar desde un clon vacío.


Coloca tu propia copia del cliente en `client/`. Ningún archivo de esa carpeta se distribuye en este repositorio. Las herramientas propias están en `client-tools/` y se incluyen por separado. El cliente debe contener directamente `config.properties`, `classpath`, `contents/`, `lib/` y `jre/`.

Compose también requiere la captura externa indicada en su volumen `/fixtures/frames.jsonl`; `.runtime/` no se distribuye. El informe grande `docs/reports/combat-inventory/inventory.json` se incluye comprimido como `inventory.json.gz`.

Client tools usage and requirements: [client-tools/README.md](client-tools/README.md).

## Arranque local

Desde esta carpeta:

```bash
git lfs pull
python3 tools/prepare-local-runtime.py
bash tools/build-local.sh
docker compose up -d
docker compose ps
bash client-tools/client.sh play
```

Para abrir otra instancia: `bash client-tools/client.sh play --profile nombre`.

```bash
docker compose logs -f world
PYTHONPATH=server python3 -m unittest discover -s server/tests
```

El servidor usa PostgreSQL en el servicio `postgres`, base `wakemu_runtime`, con volumen persistente `postgres-data`. El entrypoint aplica las migraciones de `server/migrations/` antes de arrancar; las credenciales se leen desde el archivo privado configurado por `WAKFU_DATABASE_PASSWORD_FILE`. El archivo `.runtime/local/world.sqlite3` es histórico y no se usa como fallback ni se importa automáticamente. Los eventos detallados están en `.runtime/local/logs/game-server.jsonl`.

## Organización del servidor

The local [administration panel](docs/reports/admin-panel/README.md) is available
at <http://127.0.0.1:18084> for accounts, map inspection, server sessions, and shop
catalogue management. Its private credentials are generated separately from
game accounts. The linked guide includes access instructions and acceptance steps.

`server/local_game_server.py` conecta el protocolo con los servicios. Los módulos están en `server/wakfu_server/`:

- `combat/`: turnos, movimiento, ataques, IA, muerte y recompensas.
- `items/`: inventario, bolsas, equipamiento, builds y merkasacos.
- `maps/`: jugadores en el mundo, desplazamiento, transportes y objetos.
- `storage/`: PostgreSQL, posiciones por lotes y journal Redis de posiciones.
- `characters/`: creación, vida, experiencia, hechizos y datos sociales.

`server/ai-service/` es un proceso HTTP independiente. Compose mantiene IA y Redis en una red interna; el servidor publica los puertos del cliente solo en localhost.

El objetivo completo del emulador sigue en desarrollo. La separación de carpetas no implica que todos los sistemas del juego estén implementados.


Client version: 1.93.1+79 <- no other version compatible


## Iop repair delivery update

The shared Iop context, Preparation and voluntary-movement repairs are delivered in the complete r47 image. Current code and catalogs were verified before restart; actual Iop/Cra regressions and summon retirement checks passed. See the [delivery and validation record](docs/reports/combat-inventory/iop-shared-repair-delivery-20261009.md). Manual whole-class acceptance remains pending.


## Aniripsa local verification — 2026-10-09

Provisional manual acceptance remains **3/18** (Cra, Iop and Sacrier). Aniripsa implementation passed the final local gate: **134 tests, zero failures or skips**, including prior-class regressions. No restart or deployment was performed by this workstream. See the [implementation evidence](docs/reports/combat-inventory/aniripsa-implementation-review-20261009.md) and [complete manual acceptance test](docs/reports/combat-inventory/aniripsa-manual-acceptance-20261009.md). Aniripsa awaits manual acceptance.
