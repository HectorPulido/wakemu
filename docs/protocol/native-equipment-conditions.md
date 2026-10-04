# Criterios EQUIP y ocupaciones adicionales

`aLO.cpz()` contiene parejas de acción/criterio. `bIJ.k` las convierte mediante `fnE.valueOf` y `eQe.tz`, y `fpC.a(fnE,...)` consulta únicamente la acción solicitada. El catálogo reproducible `item-equipment-conditions.json` incluye11491referencias equipables y sus strings originales, exportados por `ExportItemEquipmentConditions.java` sin red.

El anillo2022 utiliza exactamente `EQUIP: not HasAnotherSameEquipment()`. El token204 construye `eLZ`: busca otra unidad con referencia igual y UID distinto en la selección `fpj/fpd` o equipo real `fnZ`. Las unidades repetidas que sólo están en la bolsa no cumplen esa condición. El evaluador común implementa este predicado y composición booleana/condicional; otros predicados EQUIP permanecen explícitamente rechazados. No hay regla especial por referencia2022.

`fpm.a` utiliza `fop.e` para quitar ocupaciones en conflicto y guarda sólo `fpj.c(slot_primario, UID_real)`. Las ocupaciones `fpY.gkp()` reservan slots secundarios; no exigen fabricar otra unidad ni guardar un segundo UID en la build. `validate_sheet` reserva la unión de slots primario/secundarios, rechaza colisiones en cualquiera de los órdenes, y devuelve una selección por unidad para calcular bonos una vez.

`ProbeNativeEquipmentOccupations.java` prueba template2027/Jalamartillo: `fop.b` reserva15/16; `fpi.f/eN` conserva sólo el UID101 en15 y slot16nulo. Siete pruebas de equipo verifican ownership, duplicados del anillo, criterio desconocido rechazado, colisión de ambas manos y cobertura del catálogo. La prueba antigua de rechazo indiscriminado de armas de dos manos/anillo se actualizó a comportamiento acreditado.

La localización engañosa «segunda build antes del nivel50» provino además del routing del ACK en main: `"Equipment" in reason` distingue mayúsculas, mientras los motivos de validación usan `equipment`. Esos errores caían en status2`UNAUTHORIZED`; el error de equipo válido es status7`INVALID_EQUIPMENT_SHEET`. Root coordina ese ajuste de main. No se alteraron builds o inventarios del usuario durante esta auditoría.
