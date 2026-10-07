# Aceptación completa de los canales públicos desplegados

Usar Audiluna y otro personaje en dos clientes. Grupo y privados ya tienen aceptación independiente. Esta prueba cubre comercio, comunidad española y reclutamiento español; gremio y otros canales no están incluidos en el despliegue actual.

1. Colocar ambos personajes en el mismo mapa. En Audiluna enviar, dejando un segundo entre mensajes:

   ```text
   /m prueba comercio A
   /c prueba comunidad A
   /r prueba reclutamiento A
   ```

   Esperado: los tres mensajes aparecen en ambos clientes con Audiluna como emisor y en sus respectivos canales. Activar la visualización de Comercio, Comunidad y Reclutamiento en las opciones del chat si están ocultos.

2. En el segundo personaje responder, con un segundo entre mensajes:

   ```text
   /m respuesta comercio B
   /c respuesta comunidad B
   /r respuesta reclutamiento B
   ```

   Esperado: ambos clientes reciben las tres respuestas con el nombre correcto del segundo personaje, sin duplicados.

3. Cambiar de mapa únicamente al segundo personaje mediante un dragopavo de viaje rápido. Repetir los tres comandos del paso1 desde Audiluna y los tres del paso2 desde el segundo personaje.

   Esperado: ambos siguen recibiendo los mensajes de los tres canales aunque estén en mapas distintos.

4. En el segundo cliente salir al selector y volver con el mismo personaje. Repetir los comandos de ambos lados.

   Esperado: funcionan los tres canales en ambas direcciones después de volver a entrar. No se exige conservar el historial anterior del chat.

Registrar cada paso como OK o indicar canal, emisor y cliente que no recibió. No cerrar el issue13 completo por estos canales: las ramas restantes conservan su estado pendiente.

Resultado2026-10-06: **PASS manual del usuario**, «todo funcionó perfecto sobre el chat» para este recorrido completo.
