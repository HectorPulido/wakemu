# Bonus de área: ecología y estadísticas no equivalen

## Causa concreta en la publicación ecológica

`send_planting_context` llama `position_context(character,open_test_policy=...)` sin conteos. `position_context` pasa mapas vacíos al bootstrap, y `planting_context.bootstrap` emite cero para cada familia. Se probó mapa879/región66601: familias vegetales1/2/10 salen0; suministrando `{1:7}` el mismo encoder publica7 para familia1. No es una medición de la población real de esa región, sino prueba del default y del contrato.

El conteo omitido afecta al input de satisfacción, pero **no se afirma que todo bonus se arregle con rellenar conteos**. La región de prueba tiene capacidades/umbrales0; no inventar un bonus que deba activarse allí. [Resultado y hashes](../27-clima-por-zona/probe-clima-y-ecologia.json).

## Consumidor nativo

12789 (`cuE`) contiene region_id, longitud/blob de familias de monstruos y longitud/blob de familias vegetales. `chl` actualiza `bRR`/`bRT`/`bRU`, condiciones de familias y propiedades visuales `protectorSatisfaction*`. Los blobs contienen count y pares int32family/int32population. Esta inicialización no es un paquete acreditado de modificadores de combate.

`equipment_stats.bonuses/effective_character` agrega equipamiento y aptitudes. No consulta estado territorial/satisfacción en esa ruta. No extender esta observación a todos los efectos o hechizos —reservados a otra sesión—. Falta encontrar la definición exacta de cada bonus y su carrier de aplicación/retiro a personajes.

## Solución concreta del servidor

Conectar conteos reales por **región y mapa/instancia**, calculados desde plantas/monstruos propios. No contar todo el mapa cuando contiene varias regiones, ni mezclar dos instancias, ni incluir una misma población una vez por cada jugador. Actualizar al plantar/cosechar/nacer/morir y enviar cambios a los miembros del territorio. El encoder mantiene familias aunque población sea0: conservar esa presencia porque también habilita la semilla nativa.

Resolver satisfacción con umbrales/versiones de cada familia y luego evaluar definiciones verificadas de bonus, fuente/nación y elegibilidad. Guardar modificadores con clave estable de fuente territorial; aplicar/retirar al entrar/salir o cambiar condición sin acumular sobre el valor ya aumentado. Mantenerlos separados de equipamiento y aptitudes, y cotejar comportamiento al iniciar/terminar combate. No reutilizar zone_challenges como cálculo de bonus: es otro sistema.

## Pendiente para cerrar

Tablas concretas de bonus, criterio de ciudadanía/nación, stacking, mensajes de efecto y transición en combate; dos jugadores y reconexión con estadísticas antes/después. La prueba de conteos no demuestra ninguna de esas reglas.
