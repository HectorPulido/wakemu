# Respuestas incorporadas y revisión pendiente

Las respuestas del usuario sustituyen los supuestos anteriores. «Revisa todo. Nada que decidir» asigna investigación al auditor; no es un bloqueo ni una invitación a volver a preguntar. Los archivos FALTANTES.md con respuestas se preservan sin sobrescribir.

## Alcance

Solo servidor: revisar, reproducir y documentar; no implementar fixes. Hechizos y sus tests están reservados a otra sesión. E11 se conserva como evidencia histórica y no se continúa su investigación aquí. No se cierra la auditoría por generar documentos o porque existan tests que pasan.

## Respuestas por issue

| ID | Respuesta del usuario |
| --- | --- |
| 00 | 1. Latencia esperada: La minima posible, no hay una latencia objetivo<br>2. Los 20 segundos eran un ejemplo (por ejemplo en combate o al luchar)<br>3. Hay que revisar que dominios tenemos, pero en si hay que tocar la base de datos lo menos posible, podemos usar como ejemplo la arquitectura de este server de dofus: /Users/hectorpulido/dofus/ai-service<br>4. Podemos persistir en disco redis cada cierto tiempo usando un hilo alterno para no relentizar nada, tambien agregar sistemas de graceful shutdown |
| 01 | 1. Debes hacer esto en un cliente, yo reproduje el error pero es mejor que tu captures todo<br>2. x2<br>3. Si cancelas no gastas, si consumes, gastas, simple y unviersal |
| 02 | 1. en server/protocol/monsters.json, revisar el family id, y revisar si hay algun is_boss<br>Ejemplo, la familia 68 es la familia de los jalatos, al plantar debe salir un jalatin que son los monstruos de nivel mas bajo, y deben crecer a jalato que es el siguiente escalon (revisa por nivel), luego a jalato de guerra, este es un proceso no determinista, es decir el jalato se puede quedar como jalato y cada escalon es mas dificil de subir que el anterior. Importante darle al jefe de mazmorra MUY poca posibilidad, por ejemplo el jalato real, que solo salga uno de cada muchisimas veces.<br>2. Tiempos de maduracion constante, configurable, pero que cada monstruo tenga una posibilidad de subir de tipo aleatoria, y que vaya bajando a medida de que suba el nivel.<br>3. Revisa si eso existe, si no, hay que eliminar el mob y cambiarlo de tipo<br>Importante: este proceso solo ocurre si hay gente en el mapa |
| 03 | 1. Familia es importante, madurez va por nivel, sexo ignoremoslo, y probabilidad 5% de posibilidades de subir de nivel cada cierto tiempo por ejemplo, pero depende del nivel actual vs el nivel del proximo monstruo<br>2. maximo 8 miembros, cada que un mob se reproduce hay posibilidad de subir en 1 al mob y posibilidad de generar un nuevo mob (para esto puedes usar la idea de las semillas)<br>3. Eliminar el respawn, no debe haber respawn artificial |
| 04 | 1. La probabilidad si no estoy mal depende del nivel del peletero/herbolario/leñador, va desde 1%, 25%, 50%, 75% y 100%<br>2. N/A, es importante no modificar el cliente<br>3. Si falla no hay xp y se consume la semilla, si lo logra, hay xp y se consume la semilla, si se cancela no hay xp ni se consume.<br>Importante: Para la formula, inventemos algo, plantar debe dar poca xp, recolectar un poco mas, craftear depende del numero de casillas de la receta, y todo modificable desde la db |
| 05 | 1. Debes hacer esto en un cliente, yo reproduje el error pero es mejor que tu captures todo<br>2. No hay tal politica por ahora<br>3. Revisa Java y el codigo del servidor |
| 06 | 1. el tiempo de etapas son constantes (igual que las plantaciones) y configurable, las etapas, hay que revisar el codigo y los fixtures que tenemos<br>2. Hay que buscar en el cdoigo y en internet<br>3. Cada etapa da cosas distintas, hay que revisar el codigo |
| 07 | 1. Hay que hacer una formula que sea modificable en la db, lo unico que hay que tener en cuenta es que al matar mobs en "peligro de extincion" de la zona, de stasis, al igual que plantar cosas cuando hay sobreproduccion. mantener el equilibrio debe darte wakfu.<br>2. Hay que revisar esto en el codigo y en internet.<br>3. Lo mismo que en la regla 1, si plantas cuando hay sobrepoblacion, stasis, si plantas cuando hay equilibro o peligro de extincion wakfu |
| 08 | 1. hablamos un poco de esto en: docs/soluciones-wakemu/04-probabilidad-de-plantacion/FALTANTES.md, hay que hacer que la curva tenga un multiplicador modificable<br>2. igual hablamos de eso en 04<br>3. Revisa el codigo |
| 09 | 1. Fijemos como lo hace dofus y clonemos eso, importante mantener en la base de datos un multiplicador<br>2. Revisar codigo e intenrnet<br>3. Revisar codigo y solucionar |
| 10 | 1. igual que 09, revisemos dofus<br>3. busquemos en internet como lo hace el juego original y que hacer |
| 11 | Revisa todo. Nada que decidir |
| 12 | 1. Revisa todo. Nada que decidir<br>2. en los desafios al salir se te rellena la vida, no hay teletransportacion, xp o duelo<br>3. el que se desconecta pierde, pero queda en el mismo mapa, posicion etc. estos desafios son amistosos |
| 13 | 1. Revisa todo. Nada que decidir |
| 14 | 1. Revisa todo. Nada que decidir<br>3. hablamos de eso en 10 y 9 |
| 15 | 1 y 2. Revisa todo. Nada que decidir<br>3. Revisa codigo e internet |
| 16 | 1, 2. Revisa todo. Nada que decidir<br>3. todo debe ser visible en tiempo real, no hay replay desde el principio |
| 17 | Revisa todo. Nada que decidir |
| 18 | Revisa todo. Nada que decidir |
| 19 | 1. de 1 a 5 pasos en un rango con cierta posibiloidad<br>2. Creo que eso ya esta funcionando<br>3. Minimo impacto posible |
| 20 | 1. un par de mobs, unicamente cuando incia el servidor, no hay una politica de refresco<br>2. Hay que buscar una forma muy eficiente de ver cuando hay gente en una zona<br>3. Revisa todo. Nada que decidir<br>Creo que hay informacion dentro del juego de que zona suele tener que monstruos |
| 21 | 1. Revisa todo. Nada que decidir |
| 22 | Revisa todo. Nada que decidir |
| 23 | Revisa todo. Nada que decidir |
| 24 | Revisa todo. Nada que decidir, te dije que buscaras, el primer item me comprueba que nisiquiera intentaste buscar o revisar de que hablo |
| 25 | 1. Revisa todo. Nada que decidir |
| 26 | 1. Revisa todo. Nada que decidir |
| 27 | 1. Revisa todo. Nada que decidir |
| 28 | 1. Revisa todo. Nada que decidir |
| 29 | 1. Revisa todo. Nada que decidir<br>Puedes empezar con mazmorras simples como la del jalato |
| 30 | 1. Revisa todo. Nada que decidir |
| 31 | 1. Revisa todo. Nada que decidir |
| 32 | 1. Admin -> todos los comandos !, jugador -> solo los permitidos, hay que poner eso modificable |
| 33 | 1. Revisa todo. Nada que decidir |
| 34 | 1. Revisa todo. Nada que decidir |
| E01 | 1. Revisa todo. Nada que decidir<br>Revisa tambien si vale la pena usar postgres en vez de sqlite |
| E02 | 1. Revisa todo. Nada que decidir |
| E03 | ya se habló en 32, todo modificable |
| E04 | 1. Revisa todo. Nada que decidir |
| E05 | 1. Revisa todo. Nada que decidir |
| E06 | 1. Revisa todo. Nada que decidir |
| E07 | 1. Revisa todo. Nada que decidir |
| E08 | 1. Revisa todo. Nada que decidir |
| E09 | 1. Ya eso lo hablamos antes |
| E10 | 1. Revisa todo. Nada que decidir |
| E11 | Revisa todo. Nada que decidir; revisión de hechizos reservada a otra sesión. |

## Reglas resultantes

- Semilla: éxito y fracaso consumen; cancelar no consume. Solo el éxito concede XP. Plantar da poca XP, recolectar más y fabricar escala con casillas; valores, curva y multiplicadores modificables en DB.
- Maduración: familia y escalones por nivel, intervalos configurables y probabilidad decreciente por escalón. Jefe excepcionalmente raro; verificar flags nativos. Proceso solo con jugadores en el mapa.
- Reproducción: hasta 8 miembros por grupo, posibilidad de aumentar nivel y generar otro miembro/grupo. Sin respawn artificial. Población inicial pequeña al arranque, sin refrescos periódicos.
- Duelo amistoso: no XP, botín ni teleport; salud completa al salir. Desconexión pierde y conserva mapa/posición.
- Espectadores: estado actual en tiempo real, sin reproducir eventos desde el inicio.
- Permisos: administrador con todos los comandos; jugador con lista configurable. Autorizar API y ejecución.
- Rendimiento: reducir costo y SQL al mínimo sin un umbral de latencia inventado. «20 segundos» era ilustrativo. Diseñar persistencia Redis en segundo plano y graceful shutdown; contrastar durabilidad y límites reales.

## Investigación, no decisiones pendientes del usuario

Los codecs, mensajes de error, defaults, referencias, fórmulas disponibles, catálogos, cobertura y concurrencia deben investigarse con código y fixtures antes de pedir nada. Separar «no inspeccionado», «investigado pero no demostrado» y «confirmado». Los sistemas aún inexistentes requieren un diseño verificable, no una afirmación de funcionalidad basada en un nombre de función.
