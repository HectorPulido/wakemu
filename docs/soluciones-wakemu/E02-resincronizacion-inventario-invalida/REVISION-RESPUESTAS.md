# Revisión actual — recuperación inválida de inventario

El cotejo y las pruebas actuales del [issue23](../23-bolso-sadida-apilado/REVISION-RESPUESTAS.md) confirman que la recuperación sigue usando13713 con un cuerpo de bolsas, mientras su consumidor espera una entidad. El parser exterior `cwY.dp` acepta el resto sin validarlo: una prueba positiva de ese parser no demuestra una recuperación válida.

El dispatcher actual comparte esta ruta entre12656/13673 (bolsos),12659 (consumo),12490 (destrucción) y12804 (movimiento). Rechazar una operación legítimamente es suficiente para alcanzar ese mensaje. La prueba SQLite del bolso12493 de una unidad en slot ocupado también alcanza la recuperación; no requiere un stack ni pérdida persistente.

La solución debe cubrir las cinco solicitudes y partir de una lectura autoritativa posterior al rollback. Verificar lease antes de publicar datos; una petición de una generación reemplazada no debe generar una respuesta sobre la sesión vigente. El adaptador `wire.minimal_entity` no resuelve por sí mismo este contrato: su módulo declara pendiente el serializer completo y depende de fronteras/hash de fixtures.

Falta acreditar el formato completo o un carrier alternativo de inventario y probar su aplicación a una entidad ya cargada, incluidos cambios optimistas del cliente. La excepción nativa histórica acredita el fallo; las pruebas actuales acreditan el constructor y sus rutas, sin una nueva interacción GUI. No se implementó una corrección.
