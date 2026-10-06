# 33. Rendirse deja bloqueados nuevos combates y transporte

Finalizar abandono una vez y liberar sesión/grupo aun con continuación nativa flag 0 observada.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Los cambios de backend para abandono, retorno, checkpoint, liberación de grupo y transición de mapa están implementados en el checkout actual. La revalidación PostgreSQL de [PRUEBAS.md](PRUEBAS.md) pasó 64 tests e incluye rollback/reintento de desconexión atómica, protección ante lease obsoleta, rechazo de conexión autocommit, abandono → transporte nativo → nuevo fight durable y desconexión sin callback desde un checkpoint terminal. La prueba combinada invoca directamente las funciones del backend; no conduce el dispatcher real ni el cliente visual, y no inyecta fallos posteriores al commit durante la limpieza del grupo/checkpoint. El issue queda con esa brecha de integración documentada, no certificado como recorrido completo.

## Dependencias

9, 10, 14, 21. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Abandonar no concede XP/kamas/drop; toda reserva y referencia de sesión quedan liberadas una vez.

## Aceptación manual adicional

El usuario confirma rendirse, regresar, utilizar Zaap hacia Astrub, entrar a otro combate, inicio por vencimiento del tiempo y Fulgor correcto. La orientación se rechazó, defecto independiente del issue18. Gate actual de rendición/retorno pendiente de repetir antes de actualizar cierre total.

## Cierre funcional

**Solucionado totalmente** para el defecto reportado: prueba manual completa del usuario y34 pruebas actuales OK (`test_combat_abandon`, `test_combat_exit_reentry`, `test_combat_lifecycle`, `test_session_cleanup`, `test_combat_health`, `test_health`) en PostgreSQL aislado/Redis15. Cubren fallo SQL con rollback/retry, fallo de encoder, callback duplicado y transporte seguido de nueva pelea durable.

Límite de la inyección automatizada: no se simula un fallo postcommit en la liberación del grupo/checkpoint del dispatcher. La GUI y sesión real se acreditan mediante la prueba del usuario, no mediante ese gate.
