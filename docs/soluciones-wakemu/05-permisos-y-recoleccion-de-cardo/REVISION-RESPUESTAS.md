# Revisión profunda: propiedad de todos los recursos vegetales

## Causa comprobada en el servidor

`planting.resource_packet` escribe `creation_time` en el campo protobuf 7 (tag 56). El descriptor nativo `zk.axp()` identifica ese campo como **ownerAccount**, no fecha. Ejecutando el serializador actual y decodificando sus bytes con `zk.cy`, una fecha `1791072000000` aparece literalmente como dueño de cuenta. Evidencia reproducida: [probe-propiedad-recursos.json](probe-propiedad-recursos.json).

`cFL` transmite el valor a `bOm`; `bOm.axu()` considera que existe propietario cuando es positivo. `cWn` compara `bOm.axv()` con `biB.cBt()` y, si difieren, evalúa restricciones que pueden devolver `bOd.kEa` (`RESOURCE_RESERVED`). Esto explica un rechazo local anterior a la solicitud de cosecha; no exige que el servidor haya enviado un error de permiso.

## Alcance general

El usuario confirma también fresnos y otros recursos. El serializador no contiene una condición específica de Cardo: lo llaman tanto la publicación de una plantación (`planting.py`) como la reconstrucción de recursos del mapa (`planting_runtime.py`). El catálogo contiene 533 recursos. La incompatibilidad del campo es común a todos los que pasan por esas rutas; no se afirma haber reproducido gráficamente cada especie ni que sea la única causa de sus acciones fallidas.

## Corrección propuesta exclusivamente en el servidor

Conservar la fecha en persistencia para crecimiento y temporizadores, sin reutilizarla como cuenta. Para recursos públicos enviar propietario 0 y nación 0; una futura propiedad privada debe tener campos separados con identificadores reales. No transformar las fechas antiguas en supuestos propietarios ni modificar el cliente. Revisar todas las emisiones y reconexiones porque corregir solo la primera publicación dejaría el fallo al volver al mapa.

La recolección vegetal sigue necesitando una ruta autoritativa para validar acción, etapa, alcance, profesión y recompensas; corregir estos bytes por sí solo no implementa la cosecha.

## Verificación pendiente y casos concretos

Probar Cardo, fresno y otra especie con personaje nuevo: plantación, crecimiento, recolección propia y de otro personaje, cambio de mapa y reconexión. Decodificar 13135 y comprobar ownerAccount=0 para recursos públicos. Diferenciar un bloqueo local sin solicitud de un rechazo real recibido del servidor. Incluir etapas sin acciones y ocupación simultánea como controles negativos. No se ha aplicado ninguna corrección al código.

## Intento gráfico y recuperación del entorno

El primer intento no pudo observar el cliente: el inspector rechazó conexión a las 20:21:19 UTC, y también rechazó conexión la API aislada 18091. No hubo clics ni captura nueva y no se cuenta como reproducción. Con autorización explícita del usuario se levantó otra instancia exclusiva, con copia de la base de auditoría y puertos world15566/dispatcher15568/API18091. Su health respondió 200 y el inspector del cliente relanzado volvió a responder. El personaje exclusivo se verificó como Audit Builds, nivel 100. La prueba de recolección gráfica está en curso; no se certifica todavía.
