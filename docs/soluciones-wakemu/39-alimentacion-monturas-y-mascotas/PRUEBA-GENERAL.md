# Prueba general de alimentación de mascotas

**Despliegue actual:** r55 ya contiene las correcciones de orden de UID y refresco equipado. Se puede repetir la prueba con una mascota elegible de un día UTC anterior. El escalado de características continúa pendiente.

**Estado:** prueba manual fallida el 9 de octubre. La fuente corrige el orden nativo de UID mascota/comida y el refresco de la ficha equipada; no repetir este recorrido hasta validar y desplegar la imagen completa corregida. Los gates históricos usaban el mismo orden erróneo que el servidor y no acreditan la petición real del cliente.

## Compatibilidad y comandos existentes

El catálogo nativo identifica al Dragopavo `18682` como modelo76: salud máxima20, XP50 por comida y `18378` está marcado como comida XP válida. Para el mismo modelo, `12284` y `13358` curan1, y `18377` cura hasta20. `item-stack-rules.json` permite `18682` solo en cantidad1 y permite apilar los alimentos. Estos valores se contrastaron con la política de la migración064 y las pruebas del catálogo.

La consola existente entiende `!item referencia cantidad`, pero es un comando de desarrollo: por defecto una cuenta normal solo puede usar `!ayuda` y `!pos`. Usa una cuenta ya autorizada para `!item` (administrador o habilitada previamente por la política); no existe un comando de chat para conceder ese permiso.

En un personaje de prueba con inventario libre, prepara la mascota y el alimento con:

```text
!item 18682 1
!item 18378 2
```

El grant del Dragopavo crea una unidad no apilada y la inicializa con `last_meal_date` del momento actual. Por ello, no alimentes con XP ese mismo día UTC: el cliente lo bloquea y el servidor también lo rechaza si recibe el opcode. La elegibilidad nativa es por fecha calendario UTC, no por las 20 horas que aparecen como `meal_min_interval_seconds` en el catálogo.

## Recorrido de XP y persistencia

Para que el recorrido positivo sea repetible sin editar la fila de una mascota, empieza antes de medianoche UTC:

1. Antes de las **23:55 UTC** (18:55 en Bogotá), entra con el personaje de prueba y ejecuta los dos comandos anteriores. No pruebes alimentación XP todavía. Anota el XP/vida de la mascota y la cantidad de Pienso universal.
2. Después de las **00:05 UTC** del día siguiente (19:05 en Bogotá, diez minutos después), abre el inventario, arrastra un Pienso universal a ese Dragopavo y confirma una unidad.
3. Esperado: la mascota gana **50 XP**, conserva salud20 y su UID/casilla; la pila de pienso baja en1. Sin cerrar la ficha equipada, debe mostrar nivel1 (50 XP / 50 XP por nivel). La ficha del inventario debe coincidir. Cierra y vuelve a abrir ambas: conservan XP50; el nivel35 del objeto base no es el nivel de la mascota.
4. Intenta ofrecer el segundo pienso ese mismo día UTC. Esperado: el cliente indica que la comida XP ya se usó y no cambia ni el XP ni la pila. La prueba de servidor aislada verifica además que el rechazo no consume comida ni crea otro recibo.
5. Sal al selector y vuelve a entrar con el mismo personaje. Esperado: mismo UID de mascota con XP50/salud20, un pienso restante y sin XP/recibos duplicados. El bootstrap restaura el estado ProtoPet desde el inventario autoritativo.

El intervalo23:55→00:05 UTC es intencional: demuestra que el límite de opcode es el cambio de fecha UTC y no una espera de20h. También puede usarse una mascota ya existente si pertenece al personaje, tiene modelo compatible y su `last_meal_date` es de una fecha UTC anterior; no hace falta crear otra.

## Equipamiento y recuperación

Después de cada resultado positivo y cada rechazo, quita y vuelve a equipar el mismo Dragopavo, monta, desmonta y monta de nuevo sin reconectar. Esperado: la mascota conserva XP/vida y se puede montar de nuevo; la comida no se resta al rechazar. Repite después de reconectar y compara. Registra por separado el cambio real de dominio elemental al equipar y quitar; ese cálculo sigue pendiente de revisión técnica y no se acredita con el texto del tooltip.

## Curación (opcional; requiere salud faltante)

No uses comida curativa con un Dragopavo sano: el servidor rechaza la acción sin consumirla. Si el personaje ya tiene una mascota propia con salud menor que20, ejecuta `!item 18377 1`, arrastra el pienso real de vitalidad a esa mascota y confirma. Esperado: salud20, XP sin cambios, mismo UID/casilla y consumo de una unidad. Para probar la curación de un punto, usa `!item 12284 1`; esperado: salud aumenta en1 sin exceder20. Ambas comidas curativas pueden usarse aunque la mascota haya comido XP en esa fecha.

No hay un comando autorizado para bajar la salud ni adelantar la fecha de comida, y esta prueba no modifica esos campos. Si no existe una mascota propia con salud faltante, la rama curativa queda pendiente de ese fixture; no se debe sustituir con SQL sobre un personaje activo.

## Requisitos antes de habilitar la sesión manual

- Una cuenta de prueba con permiso ya concedido para `!item` y espacio libre en la bolsa.
- Para XP positiva inmediata: un Dragopavo modelo76 recién creado antes del cambio de fecha UTC y pienso disponible, o una mascota compatible de fecha UTC anterior. Mascotas nuevas creadas después de medianoche UTC tendrán que esperar hasta el siguiente día UTC.
- Para probar curación: además, una mascota propia con salud actual menor que su máximo. No se comprobó que exista ahora mismo en el personaje activo.
- No iniciar combate durante la alimentación; el handler lo rechaza.

Validación automática local sin contenedores: catálogo nativo, wire, dispatch y routing, **14/14**. Las pruebas PostgreSQL/TLS históricas están resumidas en el [README del issue](README.md); la aceptación visual descrita aquí sigue pendiente.

## Repeat-feeding DEV policy acceptance

With `pet_feeding_daily_limit_enabled=false` after deployment, use an existing
compatible Dragopavo and `!item 18378 5`. Keep its pet panel open, note food
quantity and character elemental mastery, and feed one unit. Expect +50 XP,
food -1, pet level +1 immediately in both equipped panel and inventory. Wait
11 seconds and feed another unit on the same UTC date: expect another +50 XP
and food -1, with no daily rejection. At pet level2, this Dragopavo contributes
1 elemental mastery (0 at levels0/1 due to native rounding). Unequip and equip
the same mount, mount/dismount, reconnect, and verify XP, food and bonus agree.
The general default-true daily-limit acceptance above applies only when that
setting is enabled; the current DEV setting is disabled by explicit request.
