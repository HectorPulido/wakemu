# Composición de salas de Pâturages des Bouftous (WAKFU)

Consulta realizada el 7 de octubre de 2026. La versión oficial más reciente que pude verificar es WAKFU 1.93, anunciada como disponible el 22 de septiembre de 2026 por [Ankama en Steam](https://steamcommunity.com/app/215080/allnews/). Las fuentes de composición no identifican explícitamente la versión del juego a la que corresponden; por eso estos datos sirven como referencia externa, no como prueba de que la composición instalada en este checkout sea idéntica.

## Composición publicada

La [página de Gobball Pastures de Wakfu Wiki](https://wakfu.wiki.gg/wiki/Gobball_Pastures) describe una mazmorra de tres salas, nivel recomendado/rango 12–20, en Tainela (Astrub), y publica las cantidades por sala. La guía [Pâturages des Bouftous Niv.12 de MethodWakfu](https://methodwakfu.com/pvm/donjons/paturages-des-bouftous/) confirma tres salas y que el formato está previsto para un grupo de seis; fue publicada el 19 de mayo de 2025. MethodWakfu incluye un plano visual por sala, pero no ofrece coordenadas textuales de aparición.

| Sala | Criaturas publicadas | Total |
| --- | --- | ---: |
| 1 | 1 Jalatín blanco, 1 Jalatín negro, 1 Jalató, 1 Jalalínea | 4 |
| 2 | 1 Jalatín blanco, 1 Jalató, 2 Jalalíneas, 2 Jefes de guerra jalató | 6 |
| 3 (jefe) | 1 Jalató, 2 Jalalíneas, 2 Jefes de guerra jalató, 1 Jalató Real | 6 |

Las dos fuentes usan nombres ingleses o franceses; la traducción española de la tabla se cotejó contra los nombres del catálogo local de monstruos. La correspondencia exacta con las referencias que enumera la definición nativa normal es:

| Ref. monstruo | Nombre del catálogo local | Rango de nivel en `server/protocol/monsters.json` | Aparición indicada por la guía |
| ---: | --- | ---: | --- |
| 1 | Jalató | 8–12 | Salas 1, 2 y 3 |
| 2 | Jalatín negro | 4–8 | Sala 1 |
| 3 | Jefe de guerra jalató | 14–18 | Salas 2 y 3 |
| 39 | Jalatín blanco | 4–8 | Salas 1 y 2 |
| 41 | Jalalínea | 10–14 | Salas 1, 2 y 3 |
| 44 | Jalató Real | 23–28 | Sala 3 |

La definición local 90 enumera exactamente las referencias `[1, 2, 3, 39, 41, 44]`; la ruta normal usa la plantilla 91 y el mapa interior 1086. Esto está documentado en [SALAS-Y-CICLO-DE-INSTANCIA.md](../soluciones-wakemu/29-mazmorras-e-instancias/SALAS-Y-CICLO-DE-INSTANCIA.md), y la ruta exportada aparece en [`dungeon-entry-routes.json`](../../server/protocol/dungeon-entry-routes.json). El nombre, los rangos y las referencias salen de [`monsters.json`](../../server/protocol/monsters.json). Así se coteja que la lista de seis referencias del cliente corresponde a las seis especies de las tres salas publicadas; la guía no permite inferir variantes adicionales ni criaturas omitidas.

## Qué queda sin demostrar

- Los rangos de nivel son los del catálogo de especie, no el nivel efectivo de cada actor en cada sala. En particular, el rango del Jalató Real no determina si la instancia normal lo escala.
- Las páginas enlazadas muestran planos tácticos, pero no publican coordenadas de inicio por criatura. No convierto píxeles de esos planos en celdas del mapa.
- La lista nativa de miembros de la definición acredita pertenencia a la mazmorra, pero por sí sola no acredita distribución por sala, cantidades, selección de grado ni posiciones. Las cantidades de arriba son de la guía comunitaria, no del cliente nativo.
- La guía de MethodWakfu data de 2025 y no declara una versión de parche; el Wiki no fija una versión de juego para la tabla de salas. Por tanto, la coincidencia con WAKFU 1.93 debe validarse en cliente antes de sembrar encuentros productivos.
- Este reporte trata exclusivamente WAKFU. Resultados sobre “Donjon des Bouftous” de DOFUS se excluyeron: no son evidencia de esta mazmorra ni de su número de salas.

## Consecuencia para Wakemu

Hay una composición externa concreta y compatible, por especies, con la definición normal del catálogo: 4 actores en sala 1, 6 en sala 2 y 6 en sala 3, incluyendo al jefe final. Aún no es suficiente para poblar la instancia con fidelidad: faltan coordenadas validadas, niveles/grados efectivos por encuentro y confirmación de versión. La instancia debe seguir sin crear encuentros si no tiene una fuente local versionada que resuelva esos campos; no se deben deducir coordenadas o niveles a partir de la mera lista de referencias.
