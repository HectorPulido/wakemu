# E16 — Monstruos con nombre «Grupo local»

**Actualización:** corrección implementada en el serializador compartido; [evidencia y límites actuales](IMPLEMENTACION.md). El resto de este documento conserva el cotejo anterior, no describe el estado corregido.

## Síntoma y causa comprobada

El usuario muestra un monstruo de nivel 23 llamado «Grupo local». `combat/combat_monster_world.py::spawn_group` tiene ese literal como nombre por defecto y lo pasa a **cada miembro**, no solo a la identidad del grupo. `world_actor` lo codifica en la sección NAME de la apariencia NPC formato 11, enviada mediante 12608. La raza permanece como referencia separada.

Las llamadas revisadas en `local_game_server.py`, plantación y consola no proporcionan `name`; por tanto usan el literal. Se ejecutó el serializador actual y se decodificó el nombre: sin argumento devuelve «Grupo local»; con nombre explícito devuelve «Nombre de prueba», conservando referencia 5525. [Probe](probe-nombre-en-spawn.json). No es evidencia de que todos los NPC de cualquier ruta tengan ese nombre, pero explica los grupos publicados por esta ruta.

## Solución concreta del servidor

Separar nombre individual y metadatos de grupo. Resolver por referencia de cada miembro el nombre nativo/localizado o el contrato de fallback del cliente; no usar el nombre del líder para todos en un grupo mixto. Cotejar el consumidor NAME/BREED y la aceptación de nombre vacío antes de elegir estrategia: actualmente `world_actor` rechaza texto vacío. No borrar esa validación ni introducir traducciones inventadas.

Si el protocolo necesita texto explícito, incorporar catálogo por referencia e idioma, con revisión y fallback acreditado, y pasar nombres individuales al serializador. Aplicar la misma política a aparición inicial, plantación, respawn y retorno de combate; conservar IDs y roster. Evitar publicar etiquetas de depuración como nombres de juego.

## Pruebas pendientes

Cotejar consumidor nativo; dos razas en el mismo grupo; mismo monstruo antes/después de combate y reconexión; idiomas disponibles y referencia sin traducción. La captura acredita el síntoma visual, no estas variantes. No se aplicaron fixes.


## Codec nativo NAME comprobado

Se identificó `eHd.fsQ → qR`: nombre UTF-8 con longitud u16. Se ejecutó su serialización/decodificación con null, vacío, «Grupo local» y «Jalató». Null y vacío producen dos bytes cero y se decodifican como cadena vacía; el codec los acepta. El encoder del servidor impone una restricción adicional al rechazarlos. **Esto todavía no acredita que la interfaz resuelva el nombre por BREED cuando NAME está vacío**: falta cotejar observer y getter visible antes de recomendar ese fallback. [Probe nativo](probe-seccion-name-nativa.json).


## Observer y getter base cotejados

La búsqueda de consumidores del campo exacto `qR.VY` identifica `eGs`: `zm` llama directamente a `eGj.setName(VY)`. El setter base guarda el texto; `eGj.getName` lo devuelve si no es null y usa «UNDEFINED» solo para null. **La cadena vacía no activa un fallback de raza en este getter base.** Falta comprobar si la clase NPC concreta sobreescribe el getter o si la ficha visible usa otra ruta; por tanto no recomendar NAME vacío basándose solo en el codec.

Existe una fuente nativa separada de nombres por raza: `blj.getName → blj.DK(reference) → aTF.a(7,reference,...)`, con comprobaciones de referencia válida. Esa ruta acredita localización por referencia, no que se utilice automáticamente ante NAME vacío. La solución del servidor debe preservar esa distinción y evitar catálogos de nombres inventados.


## Getter NPC: vacío no resuelve la raza

Un escaneo ASM de la jerarquía `eGj` encontró overrides de `getName` en `biB` y `bje`, además del método base. `bje` es NPC (`eHj`): su getter muestra la traducción `hooded.monster` si `blf.aE(this)` lo indica; en otro caso delega en `big.getName`, heredado de `eGj`. No usa `blj.DK` para resolver una cadena vacía. Por esa ruta **enviar NAME vacío no corrige el nombre**.

La propuesta concreta pasa a resolver nombre individual por referencia e idioma en el servidor y conservar las excepciones de nombres explícitos acreditadas. Cotejar los nombres del catálogo disponible con la localización nativa y la lengua negociada; no enviar una sola etiqueta a todo el roster. Sigue pendiente la prueba visual con dos referencias/idiomas y retorno de combate. [Escaneo y límites](probe-jerarquia-getname.json).


## Fuente disponible en el servidor

`server/protocol/monsters.json` **ya contiene nombres en español** (`name_locale=es`): 2.874 referencias, 2.857 con nombre y 17 vacías. Por ejemplo 5525 es «Wonejo». Ningún registro usa las etiquetas «Grupo local»/«Monstruo local». Por tanto, para referencias con nombre español, el origen de datos existe; el serializador ignora ese campo al usar su literal por defecto.

Solución inicial concreta para sesiones españolas: resolver `REFERENCES[member["ref"]]["name"]` individualmente al publicar cada miembro; validar que no esté vacío y que quepa en u16 UTF-8, sin sustituir referencia/ID/roster. No asumir cobertura total: las 17 referencias vacías requieren cotejar localización/fallback antes de publicarlas con un nombre inventado. Para otros idiomas hace falta catálogo acreditado por locale o política explícita de fallback.

`protocol_codec.py` decodifica idioma en 22954 y 13003, y máscara/ID en 12010. La búsqueda dirigida en dispatcher/almacenamiento no encontró uso de `language`/`locale`; falta seguir handlers reales y distinguir idioma de chat de localización. No usar automáticamente `language_id` como código de catálogo. [Conteos, referencias vacías y hash](probe-catalogo-nombres-servidor.json).


## Propuesta probada en roster mixto

Se serializaron dos actores del mismo grupo sintético 300 con el roster completo: referencia 5525 «Wonejo» y 4168 «Dragonito vivaz», a sus niveles mínimos válidos. `world_actor` recibe nombres explícitos diferentes y preserva referencias, ID de grupo y ambos miembros del roster. El grupo es un fixture de contraste, no población oficial. Esto demuestra que el serializador individual permite la solución; `spawn_group` aún debe admitir resolución por miembro en una implementación posterior. No se aplicó ese cambio ni se probó broadcast/UI. [Probe](probe-nombres-por-referencia.json).


## Confirmación del usuario — 6 de octubre

**Solucionado totalmente.** El usuario confirma E16 como solucionado: los monstruos muestran sus nombres reales.
