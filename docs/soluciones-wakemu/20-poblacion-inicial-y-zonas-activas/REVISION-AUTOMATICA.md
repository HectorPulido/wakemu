# Revisión manual del catálogo automático — Issue 20

Guía de campo generada desde el catálogo fuente vigente. Es una referencia para revisar en cliente los 93 hábitats preparados; no cambia el catálogo ni certifica por sí sola el acceso público de cada mapa. Los nombres solo se muestran cuando el inventario revisado tiene una etiqueta respaldada: Astrub (527) y Tierras Salvajes (711). Los demás se identifican por su ID, sin inferir nombres.

## Alcance y excepciones

- Fuente: [`initial-monster-population.json`](../../../server/protocol/initial-monster-population.json), con **93 hábitats, 53 mapas y 186 miembros** (dos por hábitat).
- Los 93 planes usan referencias nativas regulares, de familia permitida, sin propiedades especiales de mundo registradas y con MP positivo. La región `455/59601` es la única excepción: no tiene referencia móvil regular sin propiedades especiales; queda sin plan, sin sustituirla por jefe o archimonstruo.
- Cada comando `!tp` apunta a una casilla nativa transitable, vecina por arista recíproca a uno de los dos monstruos, fuera de todas las celdas ocupadas por miembros del catálogo y a más de cuatro pasos Manhattan de los accesos/transports exportados. Los 88 destinos posibles conservan la misma altura; cinco usan una arista nativa de desnivel, todos dentro de la misma región.
- Para los cinco destinos con desnivel, el cliente puede renderizar la altura de llegada de forma distinta a la casilla del monstruo, aunque ambas estén conectadas por una arista del grafo nativo.
- El comando local `!tp mapa x y z` valida que la casilla exista en geometría y transiciona al mapa; requiere permiso de consola de pruebas. Consulta el contrato en [local-test-console.md](../../reports/local-test-console.md).

## Una sola prueba manual general

El catálogo y la recuperación de los93 hábitats ya se validaron automáticamente. La tabla final es una referencia para explorar; no hace falta repetir93 pruebas manuales.

1. Entra con Audiluna y escribe `!tp 527 27 3 0`. Esperado: carga Astrub, puedes caminar y ves el grupo de dos Miaumiaus de esa región (sus etapas pueden progresar por maduración). Usa `!pos` para confirmar mapa527/instancia0.
2. Escribe `!tp 546 -48 47 0`. Esperado: carga el mapa546, puedes caminar y ves el grupo inicial de dos larvas de la familia nativa. No escribas `!mob`: ya deben existir.
3. Escribe `!tp 1134 -52 -96 50`. Esperado: carga el mapa1134 y ves el grupo de dos Crujibolas de la región79201; puedes caminar normalmente.
4. Cambia de personaje y vuelve a Audiluna. Esperado: posición/mapa coherentes; los grupos siguen existiendo una sola vez, sin duplicarse por volver a entrar. Puedes repetir los tres comandos para recorrer la misma ruta, sin crear monstruos.
5. Indica si el recorrido completo funcionó o en qué comando apareció un problema de carga, grupo o movimiento. El resto de mapas puede revisarse libremente usando la tabla, como inspección de distribución posterior.

Las celdas de los monstruos se muestran como `(x, y, z)`. La última columna da el destino manual fuera de ambos miembros; es vecino directo de la casilla indicada y el comando completo se puede pegar en el chat de pruebas.

| Mapa | Región | Ref. y nombre nativo | Nivel | Casillas de los dos miembros | Vecino libre conectado | Comando |
|---|---:|---|---:|---|---|---|
| Tierras Salvajes (711) | 63401 | 2765 — Jalató salvaje | 50 | (-27, -54, -78) + (-26, -54, -78) | (-26, -53, -78) → (-26, -54, -78) | `!tp 711 -26 -53 -78` |
| Astrub (527) | 66701 | 2616 — Miaumiau | 4 | (27, 4, 0) + (27, 5, 0) | (27, 3, 0) → (27, 4, 0) | `!tp 527 27 3 0` |
| Astrub (527) | 76101 | 2 — Jalatín negro | 4 | (-212, -28, 0) + (-212, -27, 0) | (-212, -26, 0) → (-212, -27, 0) | `!tp 527 -212 -26 0` |
| Astrub (527) | 75801 | 2 — Jalatín negro | 4 | (-63, 60, 0) + (-62, 60, 0) | (-64, 60, 0) → (-63, 60, 0) | `!tp 527 -64 60 0` |
| Astrub (527) | 76001 | 4079 — Arakna | 19 | (-158, 32, 0) + (-157, 32, 0) | (-159, 32, 0) → (-158, 32, 0) | `!tp 527 -159 32 0` |
| Astrub (527) | 75701 | 6 — Bebé tofu | 4 | (-77, -68, 0) + (-76, -68, 0) | (-76, -69, 0) → (-76, -68, 0) | `!tp 527 -76 -69 0` |
| Astrub (527) | 76201 | 2616 — Miaumiau | 4 | (-13, 138, 0) + (-13, 139, 0) | (-14, 138, 0) → (-13, 138, 0) | `!tp 527 -14 138 0` |
| Astrub (527) | 75901 | 3212 — Rata esqueleto | 19 | (47, 91, 0) + (48, 91, 0) | (46, 91, 0) → (47, 91, 0) | `!tp 527 46 91 0` |
| Astrub (527) | 75601 | 87 — Pío rojo | 22 | (4, -143, 40) + (5, -143, 40) | (5, -142, 40) → (5, -143, 40) | `!tp 527 5 -142 40` |
| ID 1134 (sin etiqueta verificada) | 79001 | 1166 — Maltrahzero | 97 | (-38, 68, 0) + (-37, 68, 0) | (-37, 69, 0) → (-37, 68, 0) | `!tp 1134 -37 69 0` |
| ID 1134 (sin etiqueta verificada) | 79201 | 4512 — Crujibola | 38 | (-53, -97, 50) + (-52, -97, 50) | (-52, -96, 50) → (-52, -97, 50) | `!tp 1134 -52 -96 50` |
| ID 1134 (sin etiqueta verificada) | 79101 | 135 — Mala semilla de girasol | 38 | (72, -15, 0) + (72, -14, 0) | (72, -13, 0) → (72, -14, 0) | `!tp 1134 72 -13 0` |
| ID 323 (sin etiqueta verificada) | 56401 | 1787 — Ratíquita | 70 | (-72, -62, 0) + (-72, -61, 0) | (-72, -60, 0) → (-72, -61, 0) | `!tp 323 -72 -60 0` |
| ID 327 (sin etiqueta verificada) | 56601 | 1829 — Murciego | 83 | (-107, -30, -20) + (-107, -29, -20) | (-106, -30, -20) → (-107, -30, -20) | `!tp 327 -106 -30 -20` |
| ID 458 (sin etiqueta verificada) | 61501 | 2462 — Gusano cherniego inmaduro | 83 | (-72, 0, 0) + (-71, 0, 0) | (-70, 0, 0) → (-71, 0, 0) | `!tp 458 -70 0 0` |
| ID 504 (sin etiqueta verificada) | 60601 | 2359 — Glalito | 98 | (-43, -94, 6) + (-42, -94, 6) | (-41, -94, 5) → (-42, -94, 6) (desnivel nativo) | `!tp 504 -41 -94 5` |
| ID 507 (sin etiqueta verificada) | 60701 | 2364 — Cuermut | 98 | (-22, -78, 28) + (-22, -77, 28) | (-22, -76, 30) → (-22, -77, 28) (desnivel nativo) | `!tp 507 -22 -76 30` |
| ID 508 (sin etiqueta verificada) | 60801 | 2350 — Mekabra | 110 | (-56, 10, 0) + (-56, 11, 0) | (-56, 12, 0) → (-56, 11, 0) | `!tp 508 -56 12 0` |
| ID 546 (sin etiqueta verificada) | 62201 | 123 — Larva azul | 8 | (-48, 45, 0) + (-48, 46, 0) | (-48, 47, 0) → (-48, 46, 0) | `!tp 546 -48 47 0` |
| ID 792 (sin etiqueta verificada) | 64601 | 2967 — Escorpico | 115 | (-144, -55, 21) + (-143, -55, 21) | (-144, -54, 20) → (-144, -55, 21) (desnivel nativo) | `!tp 792 -144 -54 20` |
| ID 793 (sin etiqueta verificada) | 64801 | 3007 — Jyman | 113 | (-3, -95, 10) + (-2, -95, 10) | (-2, -96, 10) → (-2, -95, 10) | `!tp 793 -2 -96 10` |
| ID 796 (sin etiqueta verificada) | 64701 | 2975 — Matacando saltarín | 125 | (-81, 19, 20) + (-81, 20, 20) | (-81, 21, 20) → (-81, 20, 20) | `!tp 796 -81 21 20` |
| ID 843 (sin etiqueta verificada) | 65301 | 3076 — Bulldaga enano | 143 | (-4, -4, 48) + (-4, -3, 48) | (-3, -4, 48) → (-4, -4, 48) | `!tp 843 -3 -4 48` |
| ID 853 (sin etiqueta verificada) | 65401 | 3090 — Cofrosaurio | 143 | (-53, -113, 0) + (-53, -112, 0) | (-53, -111, 0) → (-53, -112, 0) | `!tp 853 -53 -111 0` |
| ID 922 (sin etiqueta verificada) | 69301 | 3395 — Ordagova | 158 | (-36, 60, -20) + (-36, 61, -20) | (-35, 60, -20) → (-36, 60, -20) | `!tp 922 -35 60 -20` |
| ID 923 (sin etiqueta verificada) | 69401 | 3392 — Mento | 158 | (-36, 60, -20) + (-36, 61, -20) | (-36, 62, -20) → (-36, 61, -20) | `!tp 923 -36 62 -20` |
| ID 943 (sin etiqueta verificada) | 69501 | 1784 — Cuerbakesino | 65 | (-160, 43, -30) + (-160, 44, -30) | (-159, 43, -30) → (-160, 43, -30) | `!tp 943 -159 43 -30` |
| ID 943 (sin etiqueta verificada) | 69601 | 3573 — Grala | 68 | (-221, -30, 0) + (-220, -30, 0) | (-219, -30, 0) → (-220, -30, 0) | `!tp 943 -219 -30 0` |
| ID 999 (sin etiqueta verificada) | 71501 | 3857 — Kaníbola vudú | 173 | (-108, -95, -80) + (-107, -95, -80) | (-106, -95, -80) → (-107, -95, -80) | `!tp 999 -106 -95 -80` |
| ID 999 (sin etiqueta verificada) | 82201 | 3858 — Psikokópata | 173 | (-96, -61, -50) + (-96, -60, -50) | (-96, -59, -50) → (-96, -60, -50) | `!tp 999 -96 -59 -50` |
| ID 1053 (sin etiqueta verificada) | 73701 | 3862 — Dionatrapa | 173 | (-42, -10, -10) + (-41, -10, -10) | (-41, -9, -10) → (-41, -10, -10) | `!tp 1053 -41 -9 -10` |
| ID 1118 (sin etiqueta verificada) | 78601 | 4239 — Kralamar | 53 | (-35, -24, 0) + (-34, -24, 0) | (-33, -24, 0) → (-34, -24, 0) | `!tp 1118 -33 -24 0` |
| ID 1119 (sin etiqueta verificada) | 78701 | 4248 — Brizlochino | 83 | (-108, 5, 8) + (-107, 5, 8) | (-107, 6, 8) → (-107, 5, 8) | `!tp 1119 -107 6 8` |
| ID 1120 (sin etiqueta verificada) | 79401 | 4228 — Samaracito | 113 | (-88, -11, 0) + (-88, -10, 0) | (-87, -11, 0) → (-88, -11, 0) | `!tp 1120 -87 -11 0` |
| ID 1120 (sin etiqueta verificada) | 80601 | 4223 — Bebé perforatroz | 128 | (-197, 19, 4) + (-197, 20, 4) | (-197, 21, 4) → (-197, 20, 4) | `!tp 1120 -197 21 4` |
| ID 1122 (sin etiqueta verificada) | 79801 | 4214 — Berserkermana | 160 | (-35, -15, 4) + (-35, -14, 4) | (-34, -14, 4) → (-35, -14, 4) | `!tp 1122 -34 -14 4` |
| ID 1122 (sin etiqueta verificada) | 80001 | 4203 — Rastrejón | 187 | (36, -72, 50) + (36, -71, 50) | (37, -71, 50) → (36, -71, 50) | `!tp 1122 37 -71 50` |
| ID 1123 (sin etiqueta verificada) | 80101 | 4324 — Bolrag de Dor'Mor | 187 | (-89, -6, 40) + (-88, -6, 40) | (-87, -6, 40) → (-88, -6, 40) | `!tp 1123 -87 -6 40` |
| ID 1124 (sin etiqueta verificada) | 81001 | 4208 — Dragoloso | 188 | (-53, -83, 24) + (-52, -83, 24) | (-53, -82, 22) → (-53, -83, 24) (desnivel nativo) | `!tp 1124 -53 -82 22` |
| ID 1124 (sin etiqueta verificada) | 81101 | 4258 — Amaníaco | 188 | (-52, -97, 60) + (-52, -96, 60) | (-51, -96, 60) → (-52, -96, 60) | `!tp 1124 -51 -96 60` |
| ID 1135 (sin etiqueta verificada) | 80801 | 4716 — Peke charcoso | 109 | (-108, -40, 90) + (-108, -39, 90) | (-107, -40, 90) → (-108, -40, 90) | `!tp 1135 -107 -40 90` |
| ID 1135 (sin etiqueta verificada) | 80901 | 4749 — Don Kangwejus | 51 | (21, -103, -60) + (22, -103, -60) | (22, -104, -60) → (22, -103, -60) | `!tp 1135 22 -104 -60` |
| ID 1136 (sin etiqueta verificada) | 84301 | 4888 — Abráknido oscuro | 128 | (72, -36, -80) + (72, -35, -80) | (72, -34, -80) → (72, -35, -80) | `!tp 1136 72 -34 -80` |
| ID 1136 (sin etiqueta verificada) | 84401 | 4760 — Jabatillo | 66 | (-35, 115, -80) + (-34, 115, -80) | (-34, 116, -80) → (-34, 115, -80) | `!tp 1136 -34 116 -80` |
| ID 1136 (sin etiqueta verificada) | 84501 | 4867 — Pestruz | 68 | (-107, 95, 11) + (-107, 96, 11) | (-107, 97, 11) → (-107, 96, 11) | `!tp 1136 -107 97 11` |
| ID 1137 (sin etiqueta verificada) | 81901 | 4742 — Chafer lancero | 83 | (18, -133, 30) + (18, -132, 30) | (18, -131, 30) → (18, -132, 30) | `!tp 1137 18 -131 30` |
| ID 1137 (sin etiqueta verificada) | 82001 | 4912 — Escarabela | 81 | (36, -65, -50) + (36, -64, -50) | (37, -64, -50) → (36, -64, -50) | `!tp 1137 37 -64 -50` |
| ID 1137 (sin etiqueta verificada) | 85901 | 4777 — Blop flautista | 143 | (13, -265, 0) + (14, -265, 0) | (14, -264, 0) → (14, -265, 0) | `!tp 1137 14 -264 0` |
| ID 1207 (sin etiqueta verificada) | 83801 | 4880 — Crujibola de la mina | 38 | (-117, -25, 0) + (-116, -25, 0) | (-116, -26, 0) → (-116, -25, 0) | `!tp 1207 -116 -26 0` |
| ID 1207 (sin etiqueta verificada) | 86601 | 4534 — Elitiro | 157 | (-124, -84, 40) + (-124, -83, 40) | (-123, -83, 40) → (-124, -83, 40) | `!tp 1207 -123 -83 40` |
| ID 1208 (sin etiqueta verificada) | 84101 | 4726 — Pez alfombra | 113 | (-58, 31, 0) + (-57, 31, 0) | (-57, 32, 0) → (-57, 31, 0) | `!tp 1208 -57 32 0` |
| ID 1208 (sin etiqueta verificada) | 86801 | 2015 — Tymador desbordado | 158 | (-124, 17, 0) + (-124, 18, 0) | (-123, 17, 0) → (-124, 17, 0) | `!tp 1208 -123 17 0` |
| ID 1209 (sin etiqueta verificada) | 83901 | 4767 — Asesino encapuchado | 157 | (-34, -142, 40) + (-34, -141, 40) | (-33, -142, 40) → (-34, -142, 40) | `!tp 1209 -33 -142 40` |
| ID 1209 (sin etiqueta verificada) | 86701 | 4916 — Moskito | 68 | (-71, -68, 20) + (-70, -68, 20) | (-70, -67, 20) → (-70, -68, 20) | `!tp 1209 -70 -67 20` |
| ID 1210 (sin etiqueta verificada) | 84001 | 4883 — Chafer lancero de la mina | 83 | (-18, -121, 40) + (-18, -120, 40) | (-18, -119, 40) → (-18, -120, 40) | `!tp 1210 -18 -119 40` |
| ID 1210 (sin etiqueta verificada) | 86901 | 4920 — Patapikot | 158 | (-69, -45, 20) + (-69, -44, 20) | (-68, -44, 20) → (-69, -44, 20) | `!tp 1210 -68 -44 20` |
| ID 1252 (sin etiqueta verificada) | 88501 | 5036 — Bulbomatorral | 143 | (-35, -62, -76) + (-34, -62, -76) | (-34, -61, -76) → (-34, -62, -76) | `!tp 1252 -34 -61 -76` |
| ID 1252 (sin etiqueta verificada) | 88601 | 5043 — Pandócil | 173 | (-72, -144, -60) + (-72, -143, -60) | (-71, -143, -60) → (-72, -143, -60) | `!tp 1252 -71 -143 -60` |
| ID 1252 (sin etiqueta verificada) | 88701 | 5055 — Fantasma de tanuki chan | 188 | (18, -207, -20) + (18, -206, -20) | (19, -206, -20) → (18, -206, -20) | `!tp 1252 19 -206 -20` |
| ID 1252 (sin etiqueta verificada) | 88801 | 5049 — Plaguétido | 188 | (-164, -157, -50) + (-163, -157, -50) | (-162, -157, -50) → (-163, -157, -50) | `!tp 1252 -162 -157 -50` |
| ID 1264 (sin etiqueta verificada) | 89301 | 5113 — Minilubo | 68 | (36, -24, 0) + (37, -24, 0) | (37, -25, 0) → (37, -24, 0) | `!tp 1264 37 -25 0` |
| ID 1264 (sin etiqueta verificada) | 89401 | 5134 — Minibuhatrás | 190 | (-54, 80, 2) + (-54, 81, 2) | (-54, 82, 2) → (-54, 81, 2) | `!tp 1264 -54 82 2` |
| ID 1264 (sin etiqueta verificada) | 89501 | 5104 — Arakna peluda | 70 | (-126, -33, 60) + (-125, -33, 60) | (-125, -32, 60) → (-125, -33, 60) | `!tp 1264 -125 -32 60` |
| ID 1264 (sin etiqueta verificada) | 89701 | 5128 — Bebé gerbilinda | 173 | (75, 165, -20) + (75, 166, -20) | (76, 166, -20) → (75, 166, -20) | `!tp 1264 76 166 -20` |
| ID 1276 (sin etiqueta verificada) | 89901 | 5168 — Pinchusorio | 203 | (-72, -110, -1) + (-72, -109, -1) | (-72, -108, -1) → (-72, -109, -1) | `!tp 1276 -72 -108 -1` |
| ID 1276 (sin etiqueta verificada) | 90001 | 5187 — Zorrofrénico | 203 | (72, -152, 2) + (72, -151, 2) | (72, -150, 2) → (72, -151, 2) | `!tp 1276 72 -150 2` |
| ID 1276 (sin etiqueta verificada) | 90101 | 5175 — Caparrabias | 203 | (-144, -147, 1) + (-144, -146, 1) | (-144, -145, 1) → (-144, -146, 1) | `!tp 1276 -144 -145 1` |
| ID 1276 (sin etiqueta verificada) | 90201 | 5179 — Cangwepillo | 203 | (-72, -211, -1) + (-72, -210, -1) | (-72, -209, -1) → (-72, -210, -1) | `!tp 1276 -72 -209 -1` |
| ID 1295 (sin etiqueta verificada) | 90601 | 2075 — Susurradores ballesteros | 98 | (-198, -17, -42) + (-198, -16, -42) | (-197, -17, -42) → (-198, -17, -42) | `!tp 1295 -197 -17 -42` |
| ID 1295 (sin etiqueta verificada) | 90701 | 5240 — Kungfoso | 203 | (-270, 29, -80) + (-270, 30, -80) | (-269, 29, -80) → (-270, 29, -80) | `!tp 1295 -269 29 -80` |
| ID 1297 (sin etiqueta verificada) | 90801 | 5246 — Chocogüino | 203 | (-67, -41, 29) + (-67, -40, 29) | (-66, -41, 29) → (-67, -41, 29) | `!tp 1297 -66 -41 29` |
| ID 1298 (sin etiqueta verificada) | 90901 | 5234 — Torturbulento | 203 | (-120, -50, 40) + (-120, -49, 40) | (-120, -48, 40) → (-120, -49, 40) | `!tp 1298 -120 -48 40` |
| ID 1305 (sin etiqueta verificada) | 91201 | 5276 — Virescente | 218 | (-46, -99, 31) + (-46, -98, 31) | (-45, -98, 31) → (-46, -98, 31) | `!tp 1305 -45 -98 31` |
| ID 1309 (sin etiqueta verificada) | 91301 | 5282 — Crisálivacío | 218 | (-72, -33, 10) + (-72, -32, 10) | (-71, -33, 10) → (-72, -33, 10) | `!tp 1309 -71 -33 10` |
| ID 1326 (sin etiqueta verificada) | 91401 | 5288 — Condenador | 218 | (-171, -124, 50) + (-170, -124, 50) | (-170, -125, 50) → (-170, -124, 50) | `!tp 1326 -170 -125 50` |
| ID 1333 (sin etiqueta verificada) | 91801 | 5294 — CeEvroaint | 218 | (-68, -165, 24) + (-68, -164, 24) | (-68, -163, 24) → (-68, -164, 24) | `!tp 1333 -68 -163 24` |
| ID 1338 (sin etiqueta verificada) | 92001 | 5300 — Maestro de las tinieblas | 218 | (-196, -137, 16) + (-195, -137, 16) | (-195, -136, 16) → (-195, -137, 16) | `!tp 1338 -195 -136 16` |
| ID 1358 (sin etiqueta verificada) | 92201 | 5374 — Filibustero de Rano | 38 | (-166, 40, -51) + (-166, 41, -51) | (-166, 42, -51) → (-166, 41, -51) | `!tp 1358 -166 42 -51` |
| ID 1359 (sin etiqueta verificada) | 92301 | 5379 — Bwork incinerado | 40 | (-26, -175, -42) + (-26, -174, -42) | (-25, -175, -42) → (-26, -175, -42) | `!tp 1359 -25 -175 -42` |
| ID 1364 (sin etiqueta verificada) | 93001 | 5386 — Parraguás | 53 | (-25, -170, -38) + (-24, -170, -38) | (-24, -169, -38) → (-24, -170, -38) | `!tp 1364 -24 -169 -38` |
| ID 1365 (sin etiqueta verificada) | 92601 | 5397 — Mekano | 218 | (-124, -31, -49) + (-124, -30, -49) | (-124, -29, -47) → (-124, -30, -49) (desnivel nativo) | `!tp 1365 -124 -29 -47` |
| ID 1368 (sin etiqueta verificada) | 92901 | 5391 — Pequeño pezgajoso | 218 | (-62, 19, 0) + (-62, 20, 0) | (-61, 19, 0) → (-62, 19, 0) | `!tp 1368 -61 19 0` |
| ID 1384 (sin etiqueta verificada) | 93301 | 2553 — Zollo goldo | 128 | (-115, -72, 12) + (-115, -71, 12) | (-115, -70, 12) → (-115, -71, 12) | `!tp 1384 -115 -70 12` |
| ID 1384 (sin etiqueta verificada) | 93501 | 5470 — Cegalobolla | 128 | (-216, -151, 0) + (-216, -150, 0) | (-215, -150, 0) → (-216, -150, 0) | `!tp 1384 -215 -150 0` |
| ID 1384 (sin etiqueta verificada) | 93801 | 5477 — Chaqueador | 143 | (-180, -306, -3) + (-180, -305, -3) | (-179, -306, -3) → (-180, -306, -3) | `!tp 1384 -179 -306 -3` |
| ID 1384 (sin etiqueta verificada) | 93901 | 2565 — Pekewabbit | 128 | (-316, -202, 24) + (-315, -202, 24) | (-315, -203, 24) → (-315, -202, 24) | `!tp 1384 -315 -203 24` |
| ID 1385 (sin etiqueta verificada) | 93601 | 5455 — Wonejo | 2 | (-21, -4, 17) + (-21, -3, 17) | (-20, -4, 17) → (-21, -4, 17) | `!tp 1385 -20 -4 17` |
| ID 1390 (sin etiqueta verificada) | 93701 | 2606 — Pekewabbit huesudo | 143 | (-168, -49, -8) + (-167, -49, -8) | (-167, -50, -8) → (-167, -49, -8) | `!tp 1390 -167 -50 -8` |
| ID 1401 (sin etiqueta verificada) | 94201 | 5637 — Quimera vigilante | 233 | (-72, -88, 0) + (-71, -88, 0) | (-71, -89, 0) → (-71, -88, 0) | `!tp 1401 -71 -89 0` |
| ID 1401 (sin etiqueta verificada) | 94301 | 5630 — Terronita | 233 | (-170, -96, 12) + (-169, -96, 12) | (-168, -96, 12) → (-169, -96, 12) | `!tp 1401 -168 -96 12` |
| ID 1401 (sin etiqueta verificada) | 94401 | 5623 — Velocisesino | 233 | (-90, -158, 0) + (-90, -157, 0) | (-90, -156, 0) → (-90, -157, 0) | `!tp 1401 -90 -156 0` |
| ID 1401 (sin etiqueta verificada) | 94501 | 5643 — Vieja bwork | 233 | (0, -106, 0) + (0, -105, 0) | (1, -106, 0) → (0, -106, 0) | `!tp 1401 1 -106 0` |
| ID 1401 (sin etiqueta verificada) | 94601 | 5648 — Noxaraña | 233 | (-36, -299, 20) + (-36, -298, 20) | (-35, -298, 20) → (-36, -298, 20) | `!tp 1401 -35 -298 20` |

## Fuentes de coordenadas

Los miembros vienen del catálogo fuente. El vecino se eligió en la geometría nativa `combat-maps/<id>.json.gz` y se cotejó contra las superficies/regiones de `planting-maps/<id>.json.gz`. Los accesos considerados incluyen objetos nativos Door/Teleporter/Zaap/Drago/Boat/entradas, generic teleporters y posiciones de transporte; se aplicó un margen XY Manhattan de cuatro. La derivación y las 93 filas con verificaciones están preservadas en el artefacto privado `.runtime/reports/issue20-manual-reference-tp-cells.json` (modo `0600`).

La etiqueta del mapa no aparece en esa tabla fuente para 51 mapas; por eso esta guía usa IDs para ellos.
