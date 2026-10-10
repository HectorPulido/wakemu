# 25. Brechas dimensionales

Implementar acceso, instancia, oleadas/objetivos y cierre de brechas con progreso y rewards fiables.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

The classic DEV baseline is deployed in world r63. Hector confirmed solo admission, completion of the first wave, reaching wave two and surrender; read-only runtime evidence confirms closure and exterior return. Hector explicitly clarified this was a solo test, so no party-entry failure was reported. Full party, reconnect and victory acceptance remains pending.

Random item rewards are implemented and automatically verified in source, but migration095 and the new delivery integration are not deployed. The live reward policy remains disabled. Historical audit notes below describe earlier milestones and must not override this current status.

## Dependencias

10, 14, 15, 20, 29, 33. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Oleada/objetivo cambia una vez por evento; todos ven misma instancia y cierre terminal.

[Localización y definiciones nativas de oleadas](REVISION-RESPUESTAS.md).

## Auditoría automática 2026-10-09

[Inventario y brechas pendientes](../../reports/rifts/STATUS-20261009.md): 10 brechas públicas (7 clásicas, 3 definitivas) enlazadas exactamente con la tabla nativa147; 17 definiciones totales, con pruebas/demostraciones separadas. Ya se extrajeron pools de mobs, niveles, mapas, portales y salidas. Los pools vacíos de la definición de mazmorra no significan ausencia de datos: la composición elegible vive en `aLF`. No hay configuración funcional de estas diez brechas ni aceptación de oleadas/recompensas. Sin despliegue ni reinicio.

[Implementación en fuente y límites actuales](../../reports/rifts/IMPLEMENTATION-20261009.md): dominio durable, política DEV configurable, preparación de mobs nativos, recibos de oleadas y salida privada. 17/17 pruebas de dominio/adaptadores aprobadas; integración del dispatcher y aceptación completa siguen pendientes. No desplegado.

[Recompensas configurables DEV en fuente](../../reports/rifts/REWARDS-20261009.md): objetos aleatorios, esquirlas, sublimaciones BASIC verificadas y trajes físicos aprendibles. Recibos y entrega a bolsas/botín temporal en una transacción; XP/kamas cero, derrotas sin premios. Esta actualización de recompensas no está desplegada.

Ajuste DEV solicitado: máximo de seis miembros configurable en `settings.rift_policy.max_members` (migración096, pendiente de despliegue). Entrada, posición, roster congelado y formación se validan para la party completa; siete se rechazan sin movimiento parcial. La interfaz nativa documenta cuatro: seis es una política local explícita.

[Auditoría de héroes y prueba completa para seis](../../reports/rifts/HEROES-AND-ACCEPTANCE-20261010.md): corregido en fuente el pago a héroes inactivos bajo la sesión real del principal, con rollback del conjunto y replay sin duplicados. Definitivas continúan bloqueadas: falta consumo transaccional de sus llaves nativas. La prueba manual reportada solo cubre jugar solo hasta oleada2 y rendirse; grupo de seis y premios al sobrevivir siguen sin aceptación gráfica.
