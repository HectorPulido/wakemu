> Decisión de despliegue: **desactivado**. Ensayo sobre world `3af10843cbc6`,
> con 14 turnos completos: ataques 1/2, 4/4 y 0/8; máximo 23,593 s.
> La corrección de formato no acredita mejora de rendimiento. No activar
> sin una nueva comparación nativa que justifique el coste.
> Evidencia: `.runtime/local/e18-native-parts-owner-live-turns.json`.

# Grafo completo por fragmentos — prototipo, todavía sin activar

`native_graph_parts.py` demuestra una representación completa del mismo grafo
nativo. No está conectada al transporte ni al buscador vivo. La versión
desplegada sigue enviando el grafo plano completo; no hay otro servicio activo.

## Contrato

Cada identidad global tiene exactamente un propietario. El manifest conserva
el root, la cantidad total de nodos y todas las filas dinámicas. Cada fragmento
contiene otro grafo completo, validado y identificado por SHA-256 de sus bytes.
Los mapas traducen identidades locales a las identidades globales originales.
Compartir bytes no fusiona objetos distintos, aunque sus valores sean iguales.

| Campo | Contenido completo |
| --- | --- |
| `encoding` | `wakfu-native-graph-parts-1` |
| `root` | La referencia raíz original |
| `nodeCount` | Cantidad exacta de identidades globales |
| `dynamic` | Cada nodo que no pertenece a un fragmento, con su ID global |
| `fragments[].sha256` | Checksum de todos los bytes del grafo del fragmento |
| `fragments[].indices` | Mapa completo de ID local a ID global |
| `fragments[].emitted` | IDs locales cuyo nodo es propiedad de ese fragmento |

Los mapas se codifican como `{count, runs: [[start, length], ...]}`. Cada run
representa todos los enteros consecutivos desde `start`, durante `length`
posiciones; concatenarlos recupera la lista íntegra. No se descartan IDs.

Solo el esquema conocido y completo de `ImmutableTerrainSet`, sin campos
adicionales y con descendientes de tuplas exactas de enteros, es elegible.
Terreno con campos futuros, clases distintas o descendientes desconocidos
conserva su representación dinámica completa. Si ningún fragmento es elegible,
se conserva íntegro el formato plano original.

## Verificaciones

El lector verifica todos los bytes de cada blob y su esquema. Compara las
cantidades de índices con los nodos realmente presentes antes de expandir los
runs, verifica límites y unicidad, y exige propiedad completa de todos los IDs.
Un nodo compartido entre fragmentos debe tener la misma representación JSON
completa tras traducir sus referencias. No se usa igualdad numérica de Python:
`1`, `1.0` y `True` no son representaciones intercambiables.

Falta de blobs, corrupción, mapas inválidos, referencias fuera de rango o
propietarios ausentes rechazan el contexto completo. No se permite decidir
con un contexto parcialmente reconstruido. Nunca se instancian clases ni se
ejecutan callbacks recibidos.

## Evidencia actual

Once pruebas puras pasan contra el motor congelado de la imagen viva
`1c3bbea57e40`: bytes exactos, alias externos, ciclos, campos futuros, identidad
distinta de valores iguales, reutilización de blobs, corrupción, propiedad,
conteos falsificados y mapas inválidos. Luna escribió las pruebas y root las
confirmó, incluyendo dos regresiones adicionales.

```sh
PYTHONPATH="$PWD/.runtime/e18-fast-tuple-live-1c3bbea57e40:$PWD/server/ai-service" \
  .runtime/e18-venv/bin/python -m unittest test_native_graph_parts -q
```

Prueba con la geometría nativa real del mapa 1134 y runtime sintético mínimo:
7.075 celdas, 24.556 aristas, **73.677 nodos**. La reconstrucción conserva los
4.991.776 bytes exactos, SHA
`f7f512e8814d9d9489133b24948cee31c8f651df928b8d24820054a30b0ad93b`.
El manifest posterior ocupa 73.177 bytes gzip frente a 475.254 del grafo plano;
los dos blobs completos deben provisionarse primero y suman 5.454.506 bytes raw.
Los bytes no desaparecen: se mantienen en esos blobs más el manifest completo.

La partición desde un grafo ya plano tarda 1,243 s y la reconstrucción íntegra
1,471 s en esta prueba. **Todavía no mejora la latencia de los turnos.**
Artefacto: `.runtime/local/e18-native-parts-real-arena-runs-probe.json`.

## Trabajo necesario antes de activar

1. Emitir los fragmentos desde el encoder, conservando su mapa completo de
   identidades, sin generar primero todo el grafo plano.
2. Usar fragmentos verificados e inmutables mediante un lector virtual; evitar
   reconstruir, parsear y validar de nuevo cada nodo estático por consulta.
3. Integrar la provisión CAS completa en el SDK y el lector en AI. Conservar
   guard de fuente, fresh search por acción, FIFO y ACK nativos.
4. Comparar todos los nodos/campos/referencias con el camino plano, probar
   corrupción y concurrencia, y medir turnos completos antes de activar.

No requiere cambios nuevos en world ni en el cliente.

## Encoder directo experimental

`encode_parts(value)` genera el manifiesto durante el recorrido nativo, sin
serializar la geometría con índices globales. `identity_map` conserva todas
las identidades y rechaza referencias a índices todavía no asignados.
El blob local íntegro se conserva por identidad del fragmento inmutable en
una caché de 32 entradas; expulsar una entrada obliga a regenerar sus bytes
completos y no elimina datos del paquete. Cada snapshot genera su propio mapa.

37 pruebas dirigidas OK, 0,845 s; comparación exacta con `encode_bytes`
y reconstrucción completa. Evidencia:
`.runtime/local/e18-direct-fragment-encoder-tests.log`. El transporte activo
continúa usando el formato plano. Faltan lector virtual, provisión CAS e
integración y medición de turnos reales; esto no acredita mejora de latencia.

## Lector virtual y transporte opt-in

`read_parts` valida todas las identidades y bytes de los blobs completos;
expone una secuencia virtual con cada índice global. Los nodos se resuelven
en copias privadas. La caché verifica SHA en cada lectura y nunca reutiliza
un mapa de índices de otro snapshot. `load_graph` admite ambos formatos.

El transporte provisiona TODOS los blobs antes del manifiesto. Idempotencia
y reparación de corrupción verificadas por HTTP. Flag de banco `--parts`;
`ContextTransport.native_graph_parts` sigue False por defecto hasta medir
turnos completos.20 pruebas de formato OK sobre motor4b1; incluye rechazo
de JSON no canónico y claves duplicadas, mapas inválidos y contenido corrupto
aun tras caché caliente. No acredita mejora de turno ni aceptación manual.
