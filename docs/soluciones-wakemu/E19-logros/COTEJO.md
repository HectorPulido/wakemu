# Cotejo del sistema actual

Revisión del 5 de octubre de 2026. Fuentes identificadas por SHA-256 en el probe; otro agente modifica el servidor, por lo que debe repetirse el cotejo sobre el commit que se vaya a implementar.

## Por qué aparece el diario aunque no avancen los logros

`server/wakfu_server/wire.py::EMPTY_SECTIONS` incluye `ACHIEVEMENTS`. La ruta de entidad mínima usa la sección de `server/protocol/entity-defaults.json`: `001200000005000000000000000000000000000000`. El consumidor nativo acepta ese estado, pero contiene cero variables, logros persistidos, objetivos completados y seguimiento. No se encontró catálogo, almacenamiento ni evaluador de logros en los módulos Python del servidor. `server/protocol_codec.py` conoce algunos mensajes entrantes en el decodificador; eso no constituye handlers de juego ni entregas de recompensas. El dispatcher actual no referencia las solicitudes nativas 13175, 12533 y 13397.

El cliente carga las definiciones por `aZx`, `apw`, `aZy` y `bdK`; `bjs.zm` restaura el estado de `oN` en `bdM` y lo registra por actor en `bdF`. `bed`/`ber` calculan las vistas del diario. La separación es catálogo local + estado enviado por servidor; no hace falta cambiar la interfaz para empezar a hacerlo funcionar.

## De dónde salen los datos

| Fuente nativa | Contenido comprobado | Resultado de extracción |
| --- | --- | --- |
| `aJM`, tipo bdata 1 | Definiciones; categoría, criterios, objetivos, recompensas, tiempos y flags | 3.278 entradas |
| `aJU`, tipo 2 | Variables ID/nombre/flag `ckq` | 396 |
| `aJR`, tipo 3 | Categorías ID/padre | 481 |
| `aJS/aJT`, tipo 115 | Listas de entradas ordenadas por `cjZ` | 0 registros leídos; `115.bin` contiene 24 B |
| `aJN/aJQ` | Objetivos y listeners de variables/criterios | 6.029 objetivos; 297 listeners |
| `aJP`, `bdH` | Recompensas con tipo, parámetros y flag `ckk` | 5.593 recompensas; 19 tipos posibles |
| `i 18 n_es.jar` | Nombre 62, descripción 63, objetivos 64; objetos 15 | IDs de la captura resueltos |

Son filas del catálogo compartido de misiones/logros, no 3.278 logros visibles simultáneamente. Los 154 de la captura son el resultado de la vista nativa; no usar 154 como cantidad total ni conceder todas las entradas al iniciar sesión. Hay condiciones de nivel real, logros previos, fechas, configuración, instancia, gremio y otros ámbitos.

**5.021 objetivos tienen vacíos ambos campos de criterio del cliente.** Los listeners restantes tampoco describen todos los productores de eventos. Un objetivo sin expresión no significa «completado»: requiere reglas y eventos acreditados del servidor. Los scripts del cliente contienen escenarios y comentarios de eventos, pero funciones vacías como `scenario/2258.lua` no proporcionan la lógica autoritativa de entrenar cinco veces. No ejecutar esos Lua como un motor de reglas del servidor.

La referencia antigua `WakBox-Evolution/AchievementStorage.h` ayuda a interpretar nombres como cooldown/repeatable/shareable; su layout de objetivos difiere del JAR actual. El JAR y sus lectores actuales mandan; no portar el parser antiguo literalmente.

## Caso exacto de la captura

«Madera de jefe»: logro **4228**, categoría **69** (padre 68), recompensa **7936**, tipo **5 GIVE_PLAYER_ITEM**, parámetros **[16942, 1]**: una Gremialogema.

| Objetivo | Texto nativo |
| --- | --- |
| 8716 | Mercenario abnegado |
| 8717 | Meta-logro: Misiones automáticas, 6 a 20 |
| 8718 | Astrub, la ciudad de los mercenarios |
| 8723 | Zone of Beginners |
| 8724 | Entrenado por Gúltar |
| 8725 | Primera prima, misión de Ruel |

Las seis definiciones tienen criterios vacíos y carecen de listeners de variables exportados. Los textos acreditan la dependencia, pero **no sustituyen un mapeo formal de eventos/dependencias**. Para implementarlo: resolver cada logro/misión hijo a su ID, vincular su finalización durable al objetivo correspondiente y validar los seis antes de conceder 16942. No validar por nombre traducido, abrir la ventana o recibir una solicitud del cliente.

«Entrenado por Gúltar»: **3976**, objetivo **8539**, texto «Entrenar 5 veces con Tristepin»; recompensas **7050**, tipo 2 título **520**, y **7051**, tipo 5 **[14168,10]** (Almanicha). Hace falta acreditar el encuentro/evento de entrenamiento y registrar cinco victorias válidas distintas; «cinco» está acreditado por texto, no por una fórmula encontrada en el objetivo. «Zone of Beginners» es **177**, no una misión inferida por su nombre.

La localización española de la Gremi-O-Matic dice que crear el gremio requiere una Gremialogema obtenida con «Madera de jefe». El ID y la cantidad del premio coinciden con la definición. Esto enlaza E19 con E15; no se ha creado un gremio ni concedido ese objeto durante esta revisión.

## Dependencias resueltas y una colisión relevante

Los candidatos por texto/estructura son 8716→2461,8717→2996,8718→2175,8723→177,8724→3976,8725→3974. Esta correspondencia sirve para una especificación revisada; no se encontró una relación binaria explícita para estos seis objetivos. El tipo 115 está presente, pero devuelve cero registros, así que no aporta ese grafo.

**No resolver por nombre solamente:**2152 y 2175 se llaman «Astrub, la ciudad de los mercenarios».2175 está en categoría 69, activo por defecto, objetivo 4300 «Terminar la misión principal de Astrub».2152 está en categoría 298, tiene condición `False` y objetivo 4271 «Llevarle el merkasako al abuelito Ditocas». La estructura apunta a 2175 como hijo del metalogro; vincular 2152 por coincidencia de traducción produciría un bloqueo artificial.

«Primera prima»3974 necesita nivel real≥15 y 3973 completada para activar; objetivo 8459: hablar con Ruel ante el tribunal. Tiene 3000 kamas,7000 XP, título 518 y emote 20230 definidos. No completar 8725 por una conversación cualquiera con Ruel.2461 exige tres grupos de contratos (4867–4869);2996 requiere ocho logros de misiones automáticas. Por tanto,4228 exige varias familias de contenido, no seis toggles aislados.
