# 5. Cardo dice que el recurso pertenece a otra persona

Permitir recolección legal y emitir rechazos que correspondan al estado real del recurso.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**Solucionado totalmente.** El usuario confirma el cardo normal y su recolección funcionando. La corrección de propietario público se aplica a snapshots, plantación y crecimiento, con regresiones de Cardo/Fresno. Actividades adicionales de oficio se siguen en8.

Los apartados siguientes conservan la investigación y los gates anteriores; esta aceptación sustituye sus estados históricos pendientes.


**En revision.** El encoder del servidor enviaba `creation_time` en el campo nativo `ownerAccount`, haciendo que plantas y árboles públicos parecieran ajenos. Se corrigió el campo a `0`; la fecha sigue persistida para crecimiento. El mismo encoder publica nuevas plantas y snapshots al entrar al mapa. Regresión y gate de plantación: **18/18 pruebas OK** en Docker con PostgreSQL aislado, incluidos paquetes reales de cardo60/fresno139 y snapshots. Corrección recargada; el gate ampliado de catálogo/plantación/runtime/empaquetado/contexto pasó23 pruebas.

Se exportaron desde los datos nativos las acciones de flora para las 533 referencias, asociadas a sus etapas, con oficio, nivel mínimo, duración, referencias de producto y criterios. El catálogo facilita validar qué acción pertenece al recurso y etapa actuales.

El handler de cosecha vegetal `12995`, la ocupación durable, la concesión transaccional de productos/XP y la transición del recurso ya están implementados. Sigue pendiente la aceptación completa en cliente de retirada espacial, replantación y permisos en plantas y árboles. El catálogo no acredita cantidades ni probabilidades de producto ni la XP de oficio; véanse los [límites de la exportación](REVISION-RESPUESTAS.md).

## Dependencias

1, 6, 8, 24. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Solo una cosecha por transición de recurso; ocupación temporal y propiedad no se confunden.

## Causa general comprobada

[Fecha enviada como ownerAccount: afecta plantas y árboles](REVISION-RESPUESTAS.md).


## Validación de acciones en implementación

`resource_collect.py` decodifica la petición12995 (acción y coordenadas int32), resuelve la acción únicamente dentro de la especie/etapa actual y comprueba oficio/nivel. Rechaza etapa16, recursos de monstruos, acciones de otra etapa y criterios todavía sin evaluador autoritativo. Nueve pruebas Docker OK: protobuf truncado/tipos/duplicados, coordenadas signed32, acciones por etapa de cardo/fresno, oficio y criterios rechazados sin evaluador. Este módulo aún no está conectado al dispatcher ni concede productos; no acredita una cosecha completa.


`resource_collect.prepare` también resuelve el objetivo desde PostgreSQL usando mapa/instancia del personaje con lease vigente, no datos de objetivo enviados por el cliente. Consulta el oficio persistido y exige alcance validado por el coordinador. Devuelve un snapshot para reservar/completar; no concede productos ni modifica el recurso. Gate Docker con PostgreSQL aislado:17 pruebas OK de `test_resource_collect test_planting`, incluidos lease vencido/ajeno, mapa/instancia/XY, oficio no aprendido, etapa y alcance con resultado booleano exacto. Inventario y recurso permanecen intactos durante preparación.


## Inicio de ocupación verificado

`test_resource_collect`:18 pruebas Docker OK para petición, preparación PostgreSQL, autorización e inicio/resultado. Un probe offline del parser Java `cyJ.dp` confirmó el paquete generado12230, incluidos oficio, acción, XY y campo long del inicio. Falta coordinar reservas, confirmación transaccional, productos/XP y cambios del recurso; esta prueba no sustituye la cosecha de extremo a extremo.


## Reserva durable en verificación

La nueva migración012 agrega `resource_harvest_occupations`: una reserva por recurso y personaje, token único, cuenta/generación, acción, snapshot y fechas de inicio/fin/vencimiento. El margen de confirmación se lee de `settings.resource_harvest_occupation` (default5000ms), no del entorno.

`reserve` revalida lease, posición, estado del recurso, acción y oficio antes de insertar; `cancel` solo borra la identidad exacta del ticket, incluso durante limpieza de una sesión caducada. El ticket viejo no puede cancelar uno nuevo. Gate PostgreSQL aislado aprobado:31 pruebas de ocupaciones, preparación y plantación, incluidas exclusividad concurrente, expiración, cancelación antigua y persistencia. La migración todavía no se aplicó al servidor activo; no hay handler de cosecha conectado ni concesión de productos.


El crecimiento también consulta la reserva vigente después de bloquear la fila del recurso: una ocupación activa impide modificar la etapa; cancelar o vencer la reserva permite continuar. La FK compuesta cuenta/personaje de la migración012 impide identidades discordantes incluso ante escrituras directas. Integración con crecimiento incluida en el gate31: reserva vigente bloquea maduración y cancelación/expiración permiten continuar. Fuente sin recargar hasta completar el lote.

La recarga del lote de oficios aplicó012 junto con013; servidor saludable y gate56 integrado aprobado. Reserva durable y guardas de crecimiento están cargadas. El handler12995 y la finalización de cosecha siguen pendientes: la reserva cargada no acredita una cosecha completa.

## Producto y estado final de cosecha

`harvest_inventory.grant` agrega el producto en la transacción del llamador; reutiliza stacks nativos compatibles y rechaza inventario lleno sin mutar. Ocho regresiones PostgreSQL cubren merge, overflow, aislamiento y rollback. Gate compartido con oficios/preparación:33 pruebas OK. El helper no está conectado todavía al handler12995.

El consumidor cFJ de12782 busca el recurso existente porXY: aplica stage mediante bOm.m y conserva el actor; stage0 deshabilita cosecha (`bOm.ejb` falso y cWn.gu aborta). No acredita eliminación del actor ni autoriza inventar un paquete de removal13135. El layout tiene24 bytes big-endian: i32x,i32y,i16bbl,i16stage,i64kEB,i32kEC. El cotejo adicional confirma que kEB es ownerAccount: cWn.eVy compara bOm.axv() con el ID de la cuenta actual. kEC sigue sin semántica acreditada. El paquete de actualización también debe enviar ownerAccount=0 para recursos públicos; enviar creation_time vuelve a bloquear la recolección después del crecimiento. Replantación en esa celda requiere cotejar también el consumidor13135 antes de conectar el finalizador.

## Reserva durable del actor — avance del 6 de octubre

La migración014 añade mapa, instancia y coordenadas originales del personaje a cada reserva. Sus tipos coinciden con `characters` (instancia bigint y altura smallint). Invalida las reservas anteriores que carecen de esa evidencia, sin alterar recursos ni inventarios. `reserve()` guarda la ubicación leída bajo lease; `validate_actor_position()` rechaza cambios en cualquiera de los cinco campos antes de completar. Compilación, comprobación de diff y46 pruebas PostgreSQL aisladas aprobadas. Incluyen reserva durable, los cinco cambios de posición y limpieza de reservas013→014. Migración014 aplicada en el servidor Docker saludable; las cinco columnas fueron comprobadas en PostgreSQL real. El validador todavía no tiene caller de finalización. No existe todavía el dispatcher completo ni entrega autoritativa de cosecha: el issue permanece **En revision**.

## Finalización transaccional de flora — implementación en revisión

La migración016 crea recibos de cosecha que sobreviven a la eliminación del recurso y la política local `resource_harvest_rewards`: versión1, un producto primario por éxito y transición `catalog_cvF`. Usar `cvF` como etapa destino es una decisión explícita del emulador respaldada por ejemplos correlacionados, no una regla oficial universal. Las referencias alternativas/raras del catálogo no se conceden automáticamente. La XP local de cosecha es50 antes del multiplicador global; arrancar una planta sin producto concede0.

`resource_collect.complete()` valida lease, identidad, duración/vencimiento, ubicación original del actor, snapshot del recurso, oficio y acción por etapa. Confirma producto, XP, etapa/eliminación y recibos en una transacción. Inventario lleno o configuración inválida revierte todo. Las finalizaciones repetidas/concurrentes no duplican productos ni crédito. El dispatcher12995 inicia con12230;13429 tipo3 completa o cancela, separado del resultado de monstruos tipo6. Movimiento, transporte, otra ocupación y logout cancelan la reserva. No se modifican hechizos ni mecánicas de combate. Gate inicial de integración: **71 pruebas OK**, incluidas12 de finalización; el gate ampliado de outbox y dispatcher alcanza **78 pruebas OK** en PostgreSQL aislado.

Productos se publican con12470 para stacks existentes y12471 para nuevas pilas. El consumidor nativo de13916 rechaza UID existentes: usarlo como delta o sumarlo a esos paquetes duplicaría/invalidaría el inventario. La publicación del estado conserva un outbox durable, reemplaza eventos obsoletos y confirma solo el contenido enviado; el coordinador serializa entrega con el publicador de crecimiento.

**Desplegado en imagen14d2bde3 con migraciones016/017; aceptación en juego pendiente.** La ruta cFJ→bOm.m(0,true) deshabilita cosecha pero no acredita retirada espacial. `VerifyPlantingRuntime` forzaba directamente un callback Fg.aAw: prueba su flag condicional, no que12782 lo dispare. Se corrigió el probe y el comentario de estado. Se investiga el mecanismo real de retirada antes de afirmar que se puede replantar en la misma celda. El estado general permanece **En revision**.

## Regresión de permisos durante el crecimiento

La corrección inicial cubría la creación y los snapshots 13135, pero 12782 todavía escribía `creation_time` como propietario al cambiar de etapa. Se corrigió `state_packet` para conservar el propietario público (`0`) también en crecimiento y recolección. La fecha permanece en PostgreSQL como referencia temporal de las etapas. Estado: **Cambio hecho no confirmado** para esta corrección adicional; gate de **92 pruebas OK** en PostgreSQL aislado, incluida regresión de todas las etapas catalogadas de Cardo y Fresno con fecha positiva; recarga completada en imagen14d2bde3 con DB016/017 y health PostgreSQL OK; comprobación en juego pendiente. El issue completo sigue **En revision** por la eliminación y replantación del actor nativo.

El artefacto [probe-replantacion-local.json](probe-replantacion-local.json) acredita el mapeo del consumidor, pero no demuestra que la replantación ocurra en el mismo mapa: los paquetes examinados no incluyen su identidad. Procedencia comprobada: conexiones a127.0.0.1:15556/15558, por tanto emulador local. No debe usarse como prueba de comportamiento oficial.


## Cosecha completa de Cardo confirmada en cliente

El personaje de auditoría4 cosechó su Cardo60 en etapa4, celda(-12,-9,-1), acción1475. Cliente y recibo durable acreditan1 producto11447 y+50 XP de Herbolario, total60; el recursoUID947759955203611779 desapareció de PostgreSQL. Tres intentos nativos posteriores sobre la misma celda consumieron sus semillas y fallaron con probabilidad0,01. No se afirma un éxito de replantación: falta esa rama y el recorrido de Fresno. Evidencia privada: `.runtime/local/instances/audit-profession-013/e2e-flora-cardo-harvest-replant.json`.

## Cardo y Fresno — prueba adicional del 6 de octubre

En la instancia de auditoría, Cardo60 UID2940413456108495712 recorrió1→2→3→4 con el worker activo. Tras reentrada, snapshot13135 público en(-17,18,-9), etapa4; la acción1475 entregó producto11447 y+50XP de Herbolario. Fresno139 UID7631321523612460859 tuvo snapshot13135 en la misma celda, etapa4; el menú mostró «Talar / Madera de fresno Rhys / Leñador niv.0». Acción930 entregó1 producto11438 y+50XP de Leñador. Ambos recursos fueron eliminados en PostgreSQL con recibos durables y sin ocupación residual.

Los recursos de esta prueba fueron fixtures independientes: acreditan crecimiento, publicación y cosecha; **no** acreditan éxito de plantación ni replantación nativa en esa celda. La aceptación de retirada espacial/replantación continúa pendiente.
