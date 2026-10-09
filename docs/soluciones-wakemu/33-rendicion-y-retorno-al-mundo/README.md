# 33. Rendirse deja bloqueados nuevos combates y transporte

Finalizar abandono una vez y liberar sesión/grupo aun con continuación nativa flag 0 observada.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**Cambio hecho no confirmado:** r12 (`bcfd5fe7`) desplegada en el único world, base `wakemu_runtime`, healthy y66 migraciones. Corrige rendición PvE con propietario único y aborto tras última desconexión: guarda heridas de participantes, termina la reserva exacta y retira índices solo después de persistir. No concede premios por abandono.

Evidencia actual:99/99 pruebas PostgreSQL de persistencia y116/116 pruebas puras integradas. El harness TLS real acredita duelo con ataques de ambos, vencimiento del turno,13952→12238→12925→mundo en PvE, nuevo combate en la misma sesión y desconexión/reconexión seguida de otro combate sin registro residual. Salida: `.runtime/local/world-return-update-20261007/tls-r12.log`.

[Prueba manual completa habilitada](PRUEBA-GENERAL.md). Falta aceptación visual. La rendición voluntaria de un miembro mientras otros siguen combatiendo permanece pendiente; no extrapolar el recorrido de propietario único.

La aceptación conjunta de dos cuentas para rendición individual, continuidad del compañero, observación y retorno/resincronización del mundo está preparada en [PRUEBA-COMPLETA-14-16-33-MAPA.md](../16-espectadores-y-marcadores/PRUEBA-COMPLETA-14-16-33-MAPA.md). Ejecutar solo cuando root confirme que la imagen integrada ya está lista.

## Dependencias

9, 10, 14, 21. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Abandonar no concede XP/kamas/drop; toda reserva y referencia de sesión quedan liberadas una vez.

## Aceptación manual adicional

El usuario confirma rendirse, regresar, utilizar Zaap hacia Astrub, entrar a otro combate, inicio por vencimiento del tiempo y Fulgor correcto. La orientación se rechazó, defecto independiente del issue18. Gate actual de rendición/retorno pendiente de repetir antes de actualizar cierre total.

## Aceptación histórica y regresión

La aceptación previa de combate individual quedó invalidada para PvE compartido por la regresión r9:13952 rechazaba `Shared combat abandonment is not available`; salir y volver dejaba «Fight/actor already registered». La corrección r12 supera el recorrido real de rendición y desconexión con propietario único. La cobertura PostgreSQL incluye heridas y reserva del iniciador tras desconexión de varios propietarios; todavía falta rendición voluntaria de un miembro sin terminar la pelea restante.

## Aceptación r12 en curso

El usuario confirma «rendicion ok». Falta completar desconexión, selector, nuevo combate y transporte; no cerrar el issue por este único paso. Las espadas siguen ausentes en el cliente externo, defecto original16 independiente.

El usuario confirma pasos5,6,7 correctos y «xp, drop y todo sigue correcto». Rendición del propietario único, reconexión, selector y nuevos combates aceptados en r12. La retirada multiowner permanece en desarrollo; no certificarla con esta prueba.

## Rendición de un miembro: desarrollo separado

Migración067 instalada en r16 sobre la base habitual wakemu_runtime; contenedor world saludable. Verificación de root en el contenedor world existente y base aislada wakemu_migration_test: 92/92 pruebas, sin omitidas, en 62,336 segundos. Incluye retirada individual, persistencia y recuperación del recibo de retorno, preservación del combate restante, selector y limpieza del marcador del último propietario. Validación instalada:159 pruebas de imagen,95 de persistencia y prueba TLS real aprobadas. Pendiente aceptación completa en clientes reales; una espera intermitente de142 segundos sigue en revisión. Caso completo: [prueba PvE compartido](PRUEBA-PVE-COMPARTIDO.md).

## Diagnóstico de espera intermitente

La causa del intento TLS de142 segundos sigue sin demostrarse: no hay una traza guardada que identifique espera de lock, pool o PostgreSQL. El harness ahora permite `WAKFU_TLS_GATE_TRACE=1` para registrar rol, opcode, operación, tiempo monotónico y duración, sin cuerpos ni credenciales. Tres pruebas offline verifican silencio cuando está desactivado, orden de eventos y preservación de excepciones sin filtrar texto privado. No modifica el servidor instalado ni la política de leases.
