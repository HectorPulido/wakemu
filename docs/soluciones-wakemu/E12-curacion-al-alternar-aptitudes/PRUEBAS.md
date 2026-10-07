# Pruebas

Ejecutadas: diez combinaciones, cinco daños × dos rutas de almacenamiento. Reloj fijo, regeneración deshabilitada, sin equipo ni hechizos. Los resultados reproducen la curación y la reversibilidad del máximo.

Después de la corrección, repetir 1/100/419/420/421 de daño, cambiar varias veces las aptitudes, guardar la misma hoja dos veces, reconectar y hacer flush del journal. Exigir que ninguna operación recupere daño sin un evento de curación y que no se dupliquen bonus. Añadir controles con salud completa, cero y curación explícita.

## Fixture de aceptación preparado

Personaje de auditoría `Prueba Heridas`, nivel100, sin equipo y con herida canónica100:950/1050 HP. Creado en la cuenta de pruebas del usuario sin cambiar su personaje seleccionado. Aún no acredita aceptación visual. Al añadir10 puntos de porcentaje de vida, el máximo esperado es1470 y HP1370; al retirarlos debe regresar a950/1050, sin borrar la herida. Verificar coeficiente de regeneración al seleccionar antes de iniciar el ciclo.

## Precondición pendiente para prueba manual determinista

La selección del personaje llama a `health_store.initialize(..., coefficient=1)`: la regeneración puede recuperar el primer HP a los2 segundos y luego uno cada4 segundos. Por ello, preparar950/1050 en SQL antes del login no garantiza conservar esa cifra durante la prueba. `health_store.sync` admite coeficiente0 con lease y CAS, pero no hay control administrativo expuesto que sobreviva a una reentrada. **No pedir al usuario comparar números exactos hasta controlar esta precondición.** Los gates con reloj fijo siguen acreditando invariantes del servidor; no equivalen a aceptación visual. No se añadirá una columna de producción solamente para satisfacer una fixture sin revisar una solución acotada y su limpieza.

Gate ampliado: **68 pruebas OK** en PostgreSQL aislado; guardado idéntico no acumula bonus y el ciclo950/1050→1370/1470→950/1050 conserva daño100, incluido reopen del estado final. Cobertura conjunta de equipo, nivel/recompensas, muerte, curación y ticks. No acredita todavía aceptación visual determinista.
