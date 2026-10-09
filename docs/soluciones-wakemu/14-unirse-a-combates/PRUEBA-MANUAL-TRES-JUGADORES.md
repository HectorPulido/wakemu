# Prueba manual: combate compartido con retirada y victoria

Esta prueba comprueba que varios personajes pueden entrar al mismo combate, que quien se retira vuelve a explorar sin premio y que los demás pueden continuar y recibir su propio resultado.

Usa únicamente cuentas y personajes de prueba propios. Necesitas tres clientes para el recorrido principal; al final hay una alternativa con dos. Haz la prueba cuando el responsable confirme que el mundo está listo y que el comando temporal `!mob` está habilitado para el personaje que inicia cada encuentro. No hacen falta comandos administrativos ni cambios manuales de datos.

Antes de empezar, deja A, B y C juntos en el mismo mapa, fuera de combate. En cada chat ejecuta `!pos` y confirma que los tres muestran el mismo mapa e instancia. Anota el nivel, la experiencia, las kamas y los objetos de cada personaje para compararlos al final.

## Entrada de B y C durante colocación

1. En A, crea un único Mimic de prueba y ataca al grupo para abrir la colocación:

   ```text
   !mob 4196 1 1
   ```

   A debe ver la pantalla de colocación. No pulses Listo todavía.

2. En B, haz clic derecho en las espadas del combate o en A y elige **Unirse al combate**. Acepta la confirmación si aparece. B debe entrar a la misma colocación y aparecer en una casilla libre del mismo equipo.

3. Repite desde C sobre el mismo combate. C debe entrar a esa colocación, en otra casilla libre. En las tres pantallas confirma que aparecen A, B, C y el Mimic en un único encuentro.

## Retirada de A durante colocación

4. Deja A sin marcar Listo. Marca Listo en B y C. Antes de que A esté listo, A usa **Rendirse/Abandonar combate** y confirma.

   A debe regresar al mundo. B y C deben continuar juntos contra el Mimic. A no debe recibir experiencia, kamas ni objetos por esa victoria.

5. B y C derrotan al Mimic. Cada uno debe ver su propio resultado y volver al mundo. Comprueba que ambos pueden caminar y abrir el inventario y que A tampoco queda con una ventana de combate abierta.

## Retirada de A durante la pelea

6. Inicia otro encuentro con A y repite la entrada de B y C durante colocación. Esta vez marca Listo en los tres personajes.

   Espera hasta que la pelea haya empezado y A vea el combate activo. Entonces A usa **Rendirse/Abandonar combate** y confirma.

   A debe regresar al mundo sin premio. B y C deben seguir en la misma pelea y poder completar sus turnos.

7. B y C derrotan al Mimic. Ambos deben recibir su resultado individual y volver al mundo. Comprueba otra vez que ningún panel de combate quede abierto y que A no haya recibido premio.

## Reconexión y siguiente encuentro

8. Cambia al selector y vuelve a entrar con B y C. Deben aparecer en el mundo, no volver a la pelea ya terminada. Los resultados de la pelea ganada no deben aparecer otra vez ni duplicar experiencia, kamas u objetos.

9. Con B ya en el mundo, inicia un nuevo encuentro de prueba y ataca al grupo. B debe poder abrir una nueva colocación después de la pelea anterior. Cierra ese encuentro de prueba con la acción normal de rendición para no dejarlo abierto.

## Alternativa con dos clientes

Si solo puedes usar dos clientes, repite los dos recorridos de retirada con A y B: A inicia el Mimic, B se une durante colocación; primero retira A antes de que la pelea empiece y luego repite retirando A una vez iniciada la pelea. En cada caso B debe poder ganar en solitario. Esta variante comprueba la retirada y continuación con dos participantes, pero no sustituye la entrada sucesiva de B y C del recorrido principal.

## Qué debe quedar comprobado

- B y C entran al mismo combate de A antes de que empiece la pelea y ocupan casillas distintas.
- La retirada de A funciona durante colocación y durante la pelea activa.
- Al retirarse, A vuelve a explorar y no recibe el premio del combate.
- Los supervivientes continúan, reciben cada uno su resultado y vuelven al mundo.
- Tras salir y volver a entrar, no se reabre la pelea terminada ni se duplica el premio.
- Un superviviente puede empezar un nuevo encuentro después del retorno.

No esperes cantidades fijas de experiencia, kamas u objetos: pueden variar. Si algo falla, anota el número del paso, la hora, el personaje, el texto visible y qué vieron los otros clientes. Guarda capturas de los perfiles de prueba. No reinicies clientes para compensar el fallo.
