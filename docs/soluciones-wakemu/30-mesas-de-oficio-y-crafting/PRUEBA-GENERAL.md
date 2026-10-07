# Prueba completa de fabricación y XP de oficios

**Fabricación: ejecutada por el usuario. Carga de mapas: conservada en imagen activa `6319c87d`, pendiente de confirmación visual.** Para la aceptación de carga, ejecuta únicamente la prueba conjunta al final.

Usa **Adael o Audiluna**, fuera de combate. Deja cinco casillas libres en el inventario. Anota la XP de **Herbolario** (oficio72) y cuánta **Pólvora de cañón** tienes. La cuenta debe permitir los comandos de prueba. El nombre español sale del recurso nativo `i18n_es.jar/texts_es.properties`, clave `content.43.72=Herbolario`; `Armero` es el oficio77.

1. Escribe en chat general, uno por uno:

   ```text
   !tp 1134 51 8 0
   !pos
   !item 2504 50
   !item 6363 10
   ```

   **Esperado:** el chat responde exactamente `mapa=1134 instancia=0 x=51 y=8 z=0`; recibes50 Cardos borriqueros y10 Humus. Anota las cantidades totales si ya tenías esos objetos.
2. Haz clic derecho en la mesa nativa **31511**, en51,9,0, y abre la fabricación. Busca **Pólvora de cañón** (receta2227; el recurso español `content.15.8414` muestra ese texto).

   **Esperado:** la mesa abre y la receta está disponible. Cada creación requiere5 Cardos y1 Humus, y produce1 Pólvora.
3. Selecciona cantidad **10**, inicia y pulsa **Cancelar** antes de terminar.

   **Esperado:** se detiene sin consumir ingredientes, producir Pólvora ni aumentar XP. Con la velocidad actual, ese lote dura10segundos.
4. Vuelve a abrir la mesa y fabrica cantidad **1**. Espera a que termine.

   **Esperado:** consume5 Cardos y1 Humus, entrega1 Pólvora y suma200XP de Herbolario. El intento dura aproximadamente1segundo.
5. Fabrica ahora cantidad **2**.

   **Esperado:** consume10 Cardos y2 Humus, entrega2 Pólvoras y suma400XP de Herbolario. Sumando las tres creaciones, el oficio gana600XP. Comparado con antes de los comandos `!item`, quedan35 Cardos y7 Humus adicionales,3 Pólvoras más y600XP. El nivel puede aumentar según tu XP previa.
6. Cierra la mesa y vuelve a abrirla. Abre también inventario y oficios.

   **Esperado:** las cantidades y XP coinciden con el paso5; puedes caminar y fabricar de nuevo.
7. Inicia otro lote de **7** y camina para cancelar la ocupación antes de terminar.

   **Esperado:** se interrumpe sin cambios de ingredientes, productos ni XP.
8. Regresa a la selección de personaje desde el menú normal del cliente y selecciona el mismo personaje otra vez.

   **Esperado:** conservas los resultados del paso5 y puedes volver a usar la mesa, sin trabajo residual ni recompensas duplicadas. No reinicies el servidor.

Los incrementos esperados corresponden a la configuraciónSQL actual:100XP por casilla de ingrediente, dos ingredientes distintos y multiplicador1×. La duración usa velocidad local0 y ejecución secuencial por lote. Los reintentos de paquetes, permisos y rollback se verifican automáticamente; el usuario no necesita inspeccionar recibos ni enviar paquetes.

## Prueba completa de sincronización de mesa y Zaap

Esta parte está lista para ejecutar en la imagen activa `6319c87d`, que conserva la sincronización de `13984` descrita en los README de los issues30 y35. Usa el mismo personaje fuera de combate; el comando local `!tp` ya está habilitado en el entorno de prueba. En la configuración actual `WAKFU_ALL_ZAAPS=1`, ambos destinos deben aparecer en el menú.

1. Desde chat general, escribe:

   ```text
   !tp 1134 51 8 0
   !pos
   ```

   **Esperado:** el personaje llega a Astrub1134, instancia0, celda(51,8,0); aparece y abre la mesa nativa31511 en(51,9,0). Cierra la ventana sin fabricar otra receta.
2. Escribe:

   ```text
   !tp 1134 -10 -10 -1
   !pos
   ```

   **Esperado:** queda junto al Zaap31316 de Astrub, en la llegada nativa(-10,-10,-1). El Zaap se ve y se puede abrir sin recargar el cliente.
3. Usa el menú del Zaap31316 para viajar al Zaap19249 de mapa527.

   **Esperado:** llega a(0,32,0); el Zaap19249, situado en(-1,32,0), aparece y se puede seleccionar. No se reinicia ni se vuelve a abrir el cliente.
4. Desde el Zaap19249, vuelve al Zaap31316.

   **Esperado:** regresa a Astrub en(-10,-10,-1); el Zaap31316 sigue seleccionable.
5. Usa chat general:

   ```text
   !tp 1134 51 8 0
   ```

   **Esperado:** la mesa31511 reaparece y abre tras el cambio de mapa, sin recargar el cliente. La receta, inventario y XP fabricados antes permanecen iguales.
6. Regresa a selección de personaje desde el menú normal del cliente, vuelve a entrar con el mismo personaje y espera a que cargue el mapa. Comprueba la mesa31511 y viaja otra vez con el Zaap tras `!tp 1134 -10 -10 -1`.

   **Esperado:** la mesa y ambos Zaaps están visibles y seleccionables tras reconectar. No se reinicia el servidor ni se duplica consumo, producto o XP.
