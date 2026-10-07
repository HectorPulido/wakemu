# Servicio de IA táctica Wakemu

Planificador determinista por arquetipos y capacidades. Recibe el contexto
completo y solicita previews al motor nativo; world conserva la autoridad de
combate. Sin reglas por especie, Laya ni efectos inventados.

## Estructura

```text
ai-service/
├── wakfu_ai/                 # Código del servicio y SDK montado por world
│   ├── bridge/               # Entrada del combate, transporte y coordinación con world
│   ├── context/              # Grafo, serialización, cachés y catálogo completo
│   ├── http/                 # Endpoints y límites del servidor HTTP
│   ├── native/               # Oracle, ejecución de turnos, perfiles y estadísticas
│   └── planning/             # Búsqueda, scoring, capacidades, amenazas y coordinación
├── tests/                    # Pruebas del SDK, HTTP y contratos de integración
├── scripts/                  # Provisión, aceptación y herramientas de preparación
├── benchmarks/               # Fixtures y mediciones reproducibles
│   └── results/              # Resultado histórico conservado
├── tools/java/               # Probes de protocolo y serialización
├── docs/                     # Contratos, validación, pruebas e informes
├── Dockerfile
├── rebuild.sh                # Reconstruye únicamente AI y provisiona todo el catálogo
├── server.py                 # Compatibilidad para consumidores que cargan este archivo
├── planner.py                # Compatibilidad con los consumidores del planificador
├── world_loader.py           # Loader estable y versionado que ya utiliza world
├── world_entry.py            # Entrada estable delegada a wakfu_ai.bridge
└── prepare_catalog_cache.py  # Entrada estable del comando de provisión en world
```

Los módulos internos usan imports relativos de paquete. Esto conserva el
namespace privado y la versión del SDK que carga world, sin duplicar lógica
entre entradas compatibles e implementación. Las pruebas importan el paquete
real y viven fuera del código productivo. No añadir módulos nuevos a la raíz.

## Ejecutar

Desde este directorio:

```sh
python3 -m wakfu_ai
```

Configuración: `WAKFU_AI_BIND` (predeterminado `0.0.0.0`), `WAKFU_AI_PORT`
(`8090`) y `WAKFU_AI_CONTEXT_ROOT` (`/tmp/wakfu-ai-context`). El turno completo
conserva el presupuesto de 10 s y la fracción de búsqueda 0,25. La preparación
no recorta datos ni renueva el plazo real del turno.

Desde la raíz del repositorio, reconstruir la única versión de AI:

```sh
sh server/ai-service/rebuild.sh
```

Docker conserva `COPY . /app`; incluye todo el SDK y el catálogo completo del
world vivo. El script prepara, copia, importa y sella el catálogo antes de
terminar. No reinicia world ni modifica fuentes fuera de `server/ai-service`.
El formato fragmentado experimental permanece desactivado.

## Validar

Reorganización verificada: **459 pruebas OK** sobre el motor congelado
`3af10843cbc6`, 169 imports nativos y ninguno externo; 104 archivos Python
empaquetados coinciden por SHA con las fuentes. Solo AI se reconstruyó y
reinició; world mantuvo su arranque.

Desde la raíz del repositorio:

```sh
PYTHONPATH=server:server/ai-service .runtime/e18-venv/bin/python -m unittest discover -s server/ai-service/tests -p 'test_*.py'
PYTHONPATH=server:server/ai-service .runtime/e18-venv/bin/python -m unittest tests.test_ai_service tests.test_combat_tactical_ai tests.test_combat_ai_policy
```

La suite utiliza las dependencias del motor nativo de `server/requirements.txt`.
Para comparar imágenes, congelar el motor y cargar exclusivamente sus módulos;
la evidencia de cada ejecución identifica la imagen y verifica los imports.
No confundir benchmarks privados con aceptación de animaciones en el cliente.

Ejemplo de banco nativo dentro del world activo:

```sh
docker exec -e PYTHONPATH=/app:/app/ai-service:/app/tests wakfu-local-world-1 python3 -m benchmarks.benchmark_native_concurrent --url http://ai:8090 --concurrency 1 2 4 --repeats 2 --budget 10 --cold-catalog --npc-position -5 -7 -1 --output /data/e18-native-concurrent.json
```

La preparación de world se conserva en la entrada estable
`/app/ai-service/prepare_catalog_cache.py`; los demás comandos se invocan como
módulos de `scripts` o `benchmarks`, con este directorio en `PYTHONPATH`.

## Documentación

- [Estado del sistema y pendientes E18](../../docs/soluciones-wakemu/E18-ia-tactica-enemigos/README.md).
- [Prueba manual completa](docs/PRUEBA-WORLD.md).
- [Validación](docs/VALIDACION.md).
- [Inventario del puente](docs/BRIDGE-INVENTORY.md).
- [Catálogo del contenedor](docs/CATALOGO-CONTENEDOR.md).
- [Formato fragmentado experimental](docs/FORMATO-GRAFO-FRAGMENTADO.md).
- [Historia del servicio y contratos detallados](docs/HISTORIAL-SERVICIO.md).
