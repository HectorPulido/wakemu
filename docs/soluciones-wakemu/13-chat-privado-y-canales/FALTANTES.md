# Información pendiente — 13

## Pendientes específicos

| ID | Dato o decisión | Cómo resolverlo | Impacto |
| --- | --- | --- | --- |
| 1 | Lista y permisos visibles aportados por el usuario en PRUEBAS.md y canales-chat.png; pendientes contratos binarios/routing de canales públicos y reglas de Política/Campo JcJ. | Cotejar consumidores nativos y probar emisores/destinatarios | No considerar implementado un canal por estar visible |
| 2 | Regla de offline/ignorados, eco y alcance local. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 3 | Canales de guild/nación que requieren sistemas todavía ausentes. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |

## Contactos y DND — evidencia nativa confirmada

Se cotejó el bytecode del cliente instalado (`client/lib/wakfu-client.jar`) con `javap -c -p` dentro de una imagen Docker con JDK. `Nx.a(byte, byte[])` forma el frame como longitud BE de `7 + body`, flags u8, opcode BE u16 y body. Los requests comprobados son:

| Acción cliente | Clase nativa | Opcode | Flags | Body |
| --- | --- | ---: | ---: | --- |
| Acción DND | `DoNotDisturbCommand` → `csI` | 12449 | 3 | vacío |
| Añadir amigo | `AddFriendCommand` → `aOs.jv` → `NG` | 784 | 4 | longitud u8 + bytes UTF-8 del nombre |
| Añadir ignorado | `AddIgnoreCommand` → `aOs.jx` → `NH` | 657 | 4 | longitud u8 + bytes UTF-8 del nombre |
| Quitar amigo | `RemoveFriendCommand` → `NL` | 672 | 4 | i64 BE accountId; `-1` si el cliente no resuelve el contacto local |
| Quitar ignorado | `RemoveIgnoreCommand` → `NM` | 799 | 4 | i64 BE accountId; `-1` si no lo resuelve localmente |

`ListFriendsCommand` y `ListIgnoresCommand` consultan la lista local y no emiten un request. El opcode 630 es la inicialización server→client de `fa`, con listas repetidas field 1 (amigos) y field 2 (ignorados); no se encontró un request separado para pedirlas. El consumidor 711 solo demuestra recepción/visualización de estado DND: no es prueba de un setter.

El request 12449 no contiene booleano ni valor de estado. Por tanto el codec lo modela como la acción fija nativa, sin afirmar si es toggle o cómo se guarda tras reconectar. Los layouts de los requests tampoco determinan el alcance durable de las listas ni del estado DND. No hay implementación de servidor/migración en este cambio.

### Respuestas y entidad de contacto

El descriptor Protobuf del JAR confirma `fa.friends` como repeated field 1 y `fa.ignored` como repeated field 2. Cada `eT` contiene `accountId` (field 1, int64), `accountName` (2, string), `isOnline` (4, bool), `characterName` (50, string), `notify` (51, bool), `breedId` (52, int32), `sex` (53, int32), `commentary` (54, string) y `xp` (55, int64). `accountName` e `isOnline` son requeridos por el descriptor; la prueba con Protobuf `DynamicMessage` rechazó la entrada sin ambos. El handler 630 usa `accountId` como el ID del contacto que el manager almacena y manda al quitarlo; conserva por separado nombre de cuenta y nombre de personaje.

Respuestas/actualizaciones nativas comprobadas en `chc`:

| Opcode | Clase | Layout del body | Efecto en la caché nativa |
| ---: | --- | --- | --- |
| 630 | `NT` | Protobuf `fa` | Añade entradas recibidas a categoría amigos (1) e ignorados (2) |
| 641 | `NX` | i64 BE accountId, u8-len accountName, u8-len characterName | Añade ignorado |
| 711 | `Om` | un byte; true solo si vale 1 | Muestra el estado DND recibido como 1/0; no altera la lista de contactos |
| 718 | `NS` | u8-len accountName, u8-len characterName, i64 BE accountId, i16 BE breedId, i8 sex, i64 BE xp | Añade amigo |
| 719 | `NU` | i64 BE accountId | Quita amigo por ID |
| 765 | `NY` | i64 BE accountId, u8-len accountName | Quita ignorado por ID |

La caché `aOv` es un singleton del cliente y su mapa de contactos está keyed por `aOu.Sn()`; el objeto expone cuenta (`getName`) y personaje (`xO`) por separado. Eso comprueba que el identificador nativo es de cuenta y cómo el cliente representa el contacto, pero no revela si el backend durable es por cuenta o personaje. Tampoco hay evidencia aquí del ciclo de vida de DND en el servidor.

Codec puro y pruebas golden de requests, bootstrap 630 y respuestas: [social_wire.py](../../../server/wakfu_server/social_wire.py), [test_social_wire.py](../../../server/tests/test_social_wire.py). Docker: `docker compose run --rm --no-deps --entrypoint python3 -v /Users/hectorpulido/Documents/wakfu-experiment:/workspace:ro -e PYTHONPATH=/workspace:/workspace/server:/workspace/server/tests world -m unittest test_social_wire` — **9 tests OK**.

1. Revisa todo. Nada que decidir

## Reglas para completar la especificación

No inventar fórmulas oficiales, opcodes, flags o carriers. Para una regla configurable, fijar rango, default, redondeo, límites y versión. Para mensajes, demostrar encoder/decoder con fixture y consumidor nativo; no publicar archivos propietarios. Para una política de producto, documentar la elección antes de escribir tests que la congelen.

Los pasos que dependen de estos datos siguen siendo propuestas. Se puede avanzar en medición y pruebas de regresión de piezas confirmadas sin declarar cerrado el recorrido. Actualizar el cotejo si cambia la implementación concurrente.

## Revisión del estado implementado — 7 de octubre

La nota histórica de ausencia de implementación no describe la fuente actual: `social_contacts.py` conserva listas y DND, y el dispatcher conecta630/711 y mutations784/657/672/799/12449. Los privados comprueban DND e ignorados del destinatario antes del fanout; la prueba dirigida `test_world.WorldTests.test_private_chat_social_block_denies_before_any_fanout` pasó. El gate completo local de World obtuvo31/33: dos imports de ecología requieren psycopg ausente en Python del host; no se declara gate completo aprobado. No hay evidencia nativa para extender este filtro a canales públicos; permisos de gremio/nación y Política/Campo JcJ siguen pendientes.

Verificación posterior: entorno Python aislado en `.runtime/local/verification-venv` con psycopg3.2.6; gate World/sincronización estática/Registry compartido/marcadores75/75 aprobado, incluidos los dos casos de ecología que antes no podían importar. No acredita pruebas PostgreSQL ni TLS.
