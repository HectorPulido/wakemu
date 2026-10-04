# Consola de pruebas dentro del juego

Escribe estos comandos en el chat. Las operaciones se ejecutan en la sesión del personaje conectado; si cambia la sesión, se cancelan las que aún no comenzaron. Los cambios de mundo o inventario se rechazan durante un combate.

| Comando | Qué hace |
| --- | --- |
| `!ayuda` | Muestra los comandos disponibles. |
| `!pos` | Muestra mapa, instancia y coordenadas actuales. |
| `!tp mapa x y z` | Teletransporta a una casilla transitable comprobada. |
| `!item referencia cantidad` | Añade un objeto del catálogo si hay espacio. Por ejemplo, `!item 2021 1` entrega un Amuleto de jalató e indica su UID para usar `!equip`. Esta mejora está pendiente de cargar. |
| `!mob referencia nivel cantidad` | Crea entre 1 y 8 monstruos en casillas alcanzables. El nivel debe estar dentro del rango de esa referencia. Actualmente requiere instancia 0. |
| `!equip uid slot` | Equipa una unidad propia, respetando nivel y casilla. El UID identifica la unidad concreta; no es la referencia del catálogo. |
| `!unequip slot` | Quita el equipo de esa casilla y conserva el objeto en el inventario. |
| `!nivel nivel` | Sube el nivel y guarda experiencia coherente. Vuelve a seleccionar el personaje para actualizar hechizos y puntos. Este comando está preparado en archivos, pendiente de cargar. |

Los nombres españoles están junto a las referencias en `server/protocol/monsters.json` y los catálogos `item-*.json`. Las entradas sin traducción tienen nombre `null`.

La API local permite hacer lo mismo sin tocar la interfaz:

- `GET /test/sessions`: personajes conectados y sus identificadores.
- `POST /test/command`: recibe, por ejemplo, `{"character_id":7,"command":"!pos","request_id":"consulta-1"}`.
- `GET /test/command/{handle}`: consulta si la operación está pendiente, ejecutándose, terminada, fallida o cancelada.

Si la respuesta está pendiente, consulta su `handle`. No repitas una operación de generar objetos o monstruos con otro identificador: podrías ejecutarla dos veces. `request_id` evita repeticiones mientras el recibo se conserva en esa sesión; no garantiza esa protección tras reiniciar el servidor.

La API escucha en localhost. Al generar objetos, la respuesta preparada incluye UID, referencia, cantidad y ubicación. Al generar monstruos, incluye grupo e identificadores de actores. La respuesta HTTP indica el resultado del servidor; no demuestra por sí sola que la interfaz lo haya mostrado correctamente. Las pruebas de combate compartido entre varios jugadores siguen pendientes.
