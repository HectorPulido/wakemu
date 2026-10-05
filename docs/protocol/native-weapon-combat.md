# Ataques de armas

La solicitud 12889 contiene personaje, UID del objeto equipado, casilla de equipo
y coordenadas del objetivo. No es suficiente encontrar el objeto en el inventario:
el UID debe estar en la casilla 15 de la build activa del personaje.

El cliente original valida los costes en `fcH`: `fpC.gjf()` son PA,
`gji()` son PM y `gjh()` son PW. El alcance usa `cpF()` y `cpG()`;
`gjn()` exige alineación. El ataque usa el nivel del objeto (`fnR.cmZ()`),
no el nivel del personaje. Su contenedor de efectos tiene tipo 12 e identidad
igual a la referencia del objeto. La animación es 13509.

`ExportWeaponCombat.java` exporta todas las plantillas equipables en la casilla 15
y sus árboles completos de efectos. Se conservan tanto el modo de ejecución
(`aZD`, 2 en los ataques habituales) como la variante normal/crítica (`aZR`,
0/1). Son propiedades diferentes. El conversor agrega los nombres y genera un
inventario de candidatos; esa clasificación por familias de daño no acredita
que un ataque haya pasado una prueba de ejecución o una prueba gráfica.

El catálogo incluye 1.625 plantillas. 1.549 contienen únicamente raíces de daño;
las restantes incluyen curación, estados u otras acciones. Entre los candidatos
hay armas de un objetivo, martillos y bastones con área, arcos y otras armas a
distancia. 129 candidatos requieren nivel superior a 200; la prueba debe distinguir
la ejecución del efecto de los límites actuales de personajes y equipamiento.

Muchas armas usan la familia 1083 de daño de luz. El cálculo debe reutilizar el
manejador común y la selección elemental documentada en
[native-light-damage-1083.md](native-light-damage-1083.md), conservando su evento
y su identidad original. Equipar un arma no demuestra que pueda atacar.

Los catálogos se precargan al arrancar. La preparación del ataque usa una copia
del combate y solo confirma costes, daño y paquetes si termina la transacción
completa. La auditoría y las pruebas gráficas se registran por separado en el
inventario de combate.
