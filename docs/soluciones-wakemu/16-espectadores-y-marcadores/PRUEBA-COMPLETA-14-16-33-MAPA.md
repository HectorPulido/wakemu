# Aceptación completa: unirse, observar, rendirse y resincronizar el mapa

Una sola sesión con dos clientes propios: cuenta6/personaje **PruebaVisu** (A) y cuenta7/personaje **PruebaObs** (B). No abras un tercer cliente ni uses paquetes, scripts o cambios SQL desde el cliente.

**Ejecutar solo después de que root confirme que la imagen integrada está lista, health correcto y comandos habilitados temporalmente para estas dos cuentas.** La preparación administrativa se limita a account6 y account7. Si `!mob` o `!tp` responde «comando no autorizado», detén el recorrido y reporta el mensaje; no intentes otra ruta para elevar permisos.

## Preparación

1. Inicia dos clientes y entra con PruebaVisu y PruebaObs. Déjalos juntos en Astrub, mapa1134, instancia0, fuera de combate y en el mundo público. Crea un grupo de dos mediante la interfaz nativa de grupo y verifica que cada personaje aparece como miembro del otro.
2. En ambos chats ejecuta `!ayuda` y `!pos`. Confirma que los comandos de prueba están autorizados y anota XP, nivel, kamas y objetos de A y B. Usa la misma moneda/ventana de inventario antes y después; no hace falta fijar un monto de premio.
3. Si alguno no está en el mapa correcto, llévalo a la casilla pública validada y confirma su posición:

   ```text
   !tp 1134 51 8 0
   !pos
   ```

   La respuesta de posición debe indicar `mapa=1134 instancia=0 x=51 y=8 z=0`. Desde esa casilla, desplázate junto al grupo antes de comenzar.

## Encuentro 1: observación, salida, reentrada y cierre automático

4. A crea un Mimic dulce nivel1 desde el chat:

   ```text
   !mob 4196 1 1
   ```

   A ataca al Mimic para entrar en colocación y **no** pulsa Listo todavía. B debe ver las espadas de combate en el mapa. B hace clic derecho en esas espadas y elige **Observar**. Comprueba que ve la misma colocación, pero no aparece en el roster de combatientes ni puede controlar sus turnos.
5. Desde el panel de observación, B usa la acción nativa **Salir**. Debe volver al mapa, poder moverse y abrir el inventario. Sin iniciar otra pelea, B vuelve a hacer clic derecho en las mismas espadas y selecciona **Observar** otra vez. Debe recuperar la colocación actual, sin duplicar jugadores ni combatir.
6. A pulsa Listo, completa el combate y derrota al Mimic. B permanece observando hasta el cierre. Ambos deben volver al mapa automáticamente. A puede recibir XP/kamas/botín según las tiradas; B no recibe ninguno porque solo observó. Las espadas desaparecen y ambos pueden moverse y abrir inventario.

## Encuentro 2: entrada al combate y retirada de un participante

7. A crea otro encuentro:

   ```text
   !mob 4196 1 1
   ```

   A ataca sin pulsar Listo. B usa el menú contextual del personaje de A en el panel de grupo y elige la acción nativa para **unirse al combate**. Acepta la confirmación si aparece. Ambos deben quedar en la misma colocación, con el mismo roster y equipo; no se debe abrir un segundo combate. Si la opción nativa no aparece, detén el recorrido aquí y anota el texto/estado visible.
8. A y B colocan sus personajes en celdas válidas. Pulsa Listo en ambos y espera el turno de cada uno. A ejecuta la acción de **rendirse** y confirma. A debe volver a exploración, caminar y abrir inventario; no obtiene XP, kamas ni botín de ese encuentro. B debe permanecer en el combate con el Mimic vivo, sin perder su turno ni su estado.
9. B termina el combate y derrota al Mimic. B recibe su resultado y los premios que correspondan; A no recibe premios por haberse retirado. Al terminar, B también vuelve a exploración. Ambos pueden abrir inventario y empezar otra actividad sin mensaje de combate residual.

## Encuentro 3: victoria compartida y premios por personaje

10. B crea un tercer encuentro con el mismo comando `!mob 4196 1 1`, ataca sin pulsar Listo y A se une por el menú nativo del grupo. Ambos pulsan Listo y derrotan al Mimic. Cada cliente debe mostrar el resultado privado de su personaje; ambos regresan al mundo.
11. Compara los valores con la preparación: ambos pueden cambiar de XP/nivel, kamas o inventario según la política y las tiradas. No exijas una cantidad fija. No debe haber premios duplicados al cambiar al selector y volver con ambos personajes.

## Cambio de mapa, Zaap y merkasaco

12. Con ambos fuera de combate en mapa1134, ejecuta `!pos` en los dos y confirma que se ven mutuamente. Para situar A junto al Zaap31316 usa:

   ```text
   !tp 1134 -10 -10 -1
   !pos
   ```

   A viaja con el Zaap nativo31316 de Astrub al Zaap19249 del mapa527. En mapa527 debe aparecer y poder seleccionarse el Zaap19249; B, que sigue en Astrub, ya no debe ver a A. A viaja de regreso por el Zaap19249 al31316. Después de cargar mapa1134, ambos deben volver a verse una sola vez, sin cerrar ni reiniciar clientes.
13. Repite el comando `!tp 1134 -10 -10 -1` y la ida/vuelta de Zaap con B mientras A se queda en Astrub. Verifica también que A reaparece para B y viceversa al regreso. Antes/después de cada viaje, `!pos` debe mostrar el mapa e instancia actuales; no hace falta que la posición final sea la misma celda.
14. A usa el botón nativo **Bolsa de Sadida/Merkasaco** para entrar en su merkasaco; B debe dejar de ver a A en el mundo público. A sale usando el botón nativo de salida del merkasaco. Al volver a mapa1134, A y B deben verse mutuamente y una sola vez, y A debe poder seleccionar el Zaap31316 sin recargar el cliente. Repite el ciclo con B dentro de su propio merkasaco mientras A permanece fuera.

## Criterio de aceptación

- A y B ven el mismo combate al observar o unirse; el observador nunca recibe control.
- Salir y volver a observar conserva el combate actual. El cierre normal retorna al observador al mundo sin premios.
- En un combate compartido, un personaje puede rendirse sin terminar la pelea del compañero. El retirado no recibe premios; el que termina la pelea sí recibe su propio resultado. En una victoria compartida ambos reciben sus resultados individuales.
- Tras Zaap y entrada/salida del merkasaco, cada cliente muestra los personajes que están realmente en su mapa. El retorno no deja personajes invisibles, duplicados o una ventana de combate residual.
- Ningún cliente requiere reinicio para recuperar espadas, Zaap, posición o jugadores.

Si falla un paso, anota número de paso, personaje, hora local, mensaje visible y si la otra pantalla cambió. Guarda capturas de ambas pantallas solo en el perfil de prueba. Un fallo en observar/unirse bloquea los encuentros posteriores; un fallo en el cambio de mapa se registra por separado y no se compensa reiniciando el cliente.
