# Diagnóstico — 22

## Contexto registrado

Es extremadamente importante que los objetos funcionen como debe, lo que sucede es que todos los objetos aparecen con un enorme ? que normalmente significa que el objeto no está identificado. ¿Qué implica?
* Falta de elementos y huecos: El objeto aún no ha definido de manera aleatoria sus elementos de dominio/resistencia ni sus engarces de encantamiento.
* Cómo solucionarlo: Solo debes darle doble clic al objeto (si lo tienes en el inventario) para revelar y asignar sus características.

---

La identificación de elementos en Wakfu es el proceso mediante el cual configuras las estadísticas elementales y revelas el potencial de un objeto de equipo.
Tras las actualizaciones del juego, el sistema funciona de la siguiente manera:
1. La primera identificación (Doble clic)
Cuando obtienes un objeto no identificado (con el signo ?), no puedes equipártelo de inmediato. Al hacer doble clic sobre él en tu inventario, realizas dos acciones simultáneas:
• Elige tus elementos: Se abrirá una interfaz táctica que te permite seleccionar manualmente a qué elementos (Fuego, Agua, Tierra o Aire) quieres asignar el dominio elemental y las resistencias elementales del objeto.
• Revelación de engarces: El objeto revelará de forma aleatoria sus engarces de encantamiento (entre 1 y 4 ranuras), mostrando sus formas o colores (rojo, azul, verde, amarillo).
2. Los elementos ya no son definitivos
A diferencia de versiones antiguas del juego donde dependías de la suerte o de consumir consumibles (como las transmutaciones) para cambiar los elementos, el sistema actual es totalmente libre.
• Si cambias tu rama de hechizos o tu build, puedes volver a modificar los elementos del objeto en cualquier momento.
• Solo debes hacer clic derecho sobre el ítem y pulsar el botón de asignación elemental junto a las recetas para reconfigurar sus ramas. ¡Incluso puedes hacerlo mientras estás dentro de una mazmorra sin desequiparte el objeto!

---
El sistema de encantamiento de Wakfu reemplazó la antigua forjamagia para ofrecer una personalización absoluta de tus estadísticas. A diferencia de otros RPGs, aquí no compras runas prefabricadas, sino que modificas los engastes (o engarces) propios de cada objeto usando recursos que tú mismo reciclas.
1. Anatomía de los Engastes (Engarces)
Cada objeto de equipo puede albergar entre 1 y 4 engastes. Al identificarlo por primera vez, el número otorgado es completamente aleatorio.
Existen 4 tipos de engastes representados por colores y formas geométricas, y cada uno te permite elegir entre una lista específica de estadísticas:
Color / Forma	Estadísticas Seleccionables
Rojo (Triángulo)	Dominio Cuerpo a Cuerpo, Dominio Distancia, Dominio Berserker, Iniciativa.
Azul (Cuadrado)	Dominio Elemental, Vida (PdV), Placaje, Resistencia Elemental.
Verde (Círculo)	Dominio Crítico, Dominio Espalda, Esquiva, Iniciativa, Resistencia Elemental.
Blanco (Hexágono)	Comodín: Puede albergar el efecto de cualquier otro color.
💡 Regla del Doble Bonus: Si colocas un efecto en una ranura que corresponde al rol ideal de la pieza (por ejemplo, poner estadísticas de daño en armas o escudos), el beneficio estadístico se duplica automáticamente.
2. El combustible: Las Esquirlas Mágicas
Para darle poder a un engaste necesitas Esquirlas. Estas se obtienen utilizando el icono del martillo en tu inventario para romper/reciclar objetos de equipo que no utilices.
• La cantidad de esquirlas recibidas depende del nivel y la rareza del objeto destruido.
• Puedes subir el nivel de un efecto dentro del engaste consumiendo más esquirlas directamente desde tu inventario.
• Si decides retirar un efecto para cambiarlo por otro, el juego te devuelve el 90% de las esquirlas invertidas.
3. Modificación Avanzada: El Taller de Encantamiento
Ubicado en Astrub y en las capitales de cada Nación (identificado en el mapa con un icono de pergamino dorado o una "T"). Aquí es donde alteras la estructura física de tu equipamiento.
Para realizar modificaciones avanzadas, el sistema te exige sacrificar un objeto idéntico (mismo nombre, mismo nivel y misma rareza). Al destruirlo en la interfaz del taller, obtienes 7 Cargas. Estas cargas te permiten alterar tres aspectos:
1. Aumentar el Número de Engastes: Puedes gastar cargas para intentar desbloquear la 2ª, 3ª o 4ª ranura. También existe una opción de "éxito garantizado" sacrificando directamente otro objeto similar.
2. Cambiar Colores: Si tu personaje necesita ranuras rojas pero tu coraza tiene ranuras verdes, usas cargas para cambiar aleatoriamente el color de los engastes.
3. Cambiar el Orden: Altera la posición de los colores de izquierda a derecha. Esto es vital para el paso final: el fin del juego (endgame).
4. El objetivo final: Las Sublimaciones
Las Sublimaciones son pergaminos que añaden efectos pasivos únicos y extremadamente poderosos (como ganar PA bajo ciertas condiciones, infligir más daños si atacas primero, etc.).
Para poder aplicar una sublimación a tu objeto, este debe cumplir estrictamente dos condiciones:
• Tener exactamente 3 o 4 engastes abiertos.
• Los colores de tus engastes deben coincidir en el orden exacto que exige el pergamino de sublimación (por ejemplo: Rojo-Azul-Verde). Los engastes blancos (comodines) sustituyen cualquier color requerido.


**Hipótesis de la revisión inicial (código anterior):** `items/inventory_items.py::item_proto` transmitía solo UID, referencia y cantidad; `item_form` añadía ocho bytes a cero. Faltan propiedades de instancia en el modelo mínimo, pero no se verificó cuál campo controla el estado “identificado” ni qué referencias fallan.

**Posible solución:** identificar el campo nativo y persistir sus propiedades junto con efectos/variantes que corresponda; inicializar objetos nuevos según la política deseada. **Validación:** objetos recién obtenidos, stack, equipamiento y reconexión muestran el mismo estado.

Extra: revisar tambien el funcionamiento de la forjamagia y los engastes

**Contexto del usuario y alcance técnico:** el texto anterior describe el comportamiento esperado; no acredita todavía que cada regla corresponda al cliente instalado. Separar identificación, elección de elementos, revelación de engastes, reciclaje, cargas del taller y sublimación. No son un único booleano “identificado”. El contexto menciona amarillo y después blanco para el cuarto color, y cifras como 7 cargas/90% de devolución: conservarlas como requisitos a contrastar con catálogos y protocolo antes de implementar o cobrar recursos. No se verificó aquí una tasa oficial ni se probaron esas operaciones completas.

**Cambio concurrente comprobado en el checkout:** ahora existen `items/inventory_elements.py` y sus tests, añadidos por el otro agente. `concesión` genera máscaras para efectos 1068/1069 y guarda `inventory_item_elements`; `item_proto` añade campo protobuf **56** (tag codificado 450), y `item_form` transmite la opción elemental. Es una selección aleatoria al otorgar el objeto, no la interfaz autoritativa de elección manual descrita por el usuario. La BD histórica sin esa fila conserva ausencia de elementos; no hay migración acreditada de todos los objetos viejos. Este resultado pertenece al código del checkout, no demuestra que el proceso principal ya lo haya cargado; la instancia de builds usa una copia anterior fija.

**Reproducido sin alterar objetos reales:** con referencia 2869 y RNG fijo, una nueva unidad recibió máscaras `[22,0]`: dominio Agua/Tierra/Aire y ninguna resistencia seleccionada. Reabrir la BD conservó las máscaras. La representación heredada del mismo objeto, sin propiedades de elementos, emitió solo tags 8/16/24 y ocho opciones nulas; la nueva emitió también tag 450 y diez bytes de opciones. Un probe del JAR instalado decodificó correctamente ambas máscaras mediante `kX/le` y `vj/foX`; no se modificó el cliente. Los **3 tests de elementos pasaron**, incluyendo persistencia y ausencia heredada. Esto acredita el codec y la persistencia de elementos, no la desaparición gráfica del “?” ni la existencia de engastes.

**Pendiente de implementación/verificación del servidor:** no se encontró en los módulos de items revisados un modelo persistido de colores/orden/efectos de engastes, cargas, esquirlas invertidas y sublimaciones. Destruir un objeto (`inventory_actions.destroy`) elimina el stack y emite decremento; no equivale a reciclarlo concediendo esquirlas. No deben reutilizarse esas operaciones confundiendo sus recompensas. Tampoco se identificó en el dispatcher revisado una ruta completa de selección/reasignación elemental o taller. Hace falta capturar las solicitudes concretas y validar los handlers nativos antes de asignar opcodes por suposición.

**Solución y validación ampliadas:** propiedades por UID con revisión y política explícita de identificación inicial; separar una unidad de un stack si sus propiedades pasan a ser individuales. Identificar una sola vez, persistiendo el sorteo antes del ACK; reintentar no vuelve a sortear. Aplicar selección elemental y bonus efectivos en builds y combate desde el mismo objeto. Reciclar/sacrificar debe consumir origen y conceder resultado en una única transición idempotente; validar identidad, rareza, nivel, propiedad, recursos y compatibilidad de sublimación. Probar doble clic repetido, desconexión después de confirmar y antes del ACK, inventario lleno, objeto equipado/referenciado por otra build, stack de varias unidades y flush Redis durante la operación. Ninguna de esas pruebas completas se da por aprobada por el probe de elementos.

## Lectura actual

La selección aleatoria de máscaras elementales ya tiene almacenamiento y serialización. No equivale a identificación interactiva, elección manual, sockets, cargas o sublimaciones; no describir este checkout como si no tuviera propiedades elementales.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Identificación: solicitud/ACK/campos nativos y condición exacta que dibuja?.
- Catálogos de sockets/costos/RNG/reembolsos y condiciones por versión; contexto amarillo/blanco y 90% deben contrastarse.
- Protocolo de selector, taller, reciclaje y sublimaciones; mapa/mesa concreta.
- Política de migración de items viejos y de stacks con atributos individuales.
- Efectos/running-effects de cada sublimación priorizada y restricciones durante combate/mazmorra.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
