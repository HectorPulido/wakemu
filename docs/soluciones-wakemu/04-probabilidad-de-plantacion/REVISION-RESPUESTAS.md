# Plantación: reglas respondidas y rama efectiva

## Cotejo actual

`planting.prepare` comprueba oficio mínimo y permisos, pero no calcula probabilidad. `planting.complete` inserta recurso y consumo en transacción y devuelve12954 con éxito **true**; su firma no recibe probabilidad ni tirada. En esta ruta una operación autorizada y completada no puede producir fallo aleatorio. El porcentaje visible no gobierna esa rama. Esto acredita divergencia de código, no una distribución medida en GUI. [Código actual y hash](probe-rama-exito-actual.json).

## Respuestas incorporadas

El usuario autoriza una regla configurable del emulador, sin modificar cliente: semilla consumida en éxito/fallo, XP solo en éxito, cancelación sin consumo ni XP. Los escalones1/25/50/75/100 son una sugerencia sujeta a su propia incertidumbre; no se atribuyen a una fórmula oficial.

## Integración concreta

Conservar autorización y reserva actuales. Añadir al recibo versión de política, oficio/nivel requisito, probabilidad en enteros0–10000, tirada uniforme0–9999 y resultado `draw < chance`. La política DB debe fijar tramos por diferencia nivel oficio−nivel requisito y validarlos sin solapamientos, junto a XP de plantación; no usar mínimos de oficio como porcentaje. Tomar la política al comenzar y mantenerla hasta resolver el ticket.

El fallo necesita **su propia transición transaccional**: consumir exactamente una semilla y escribir recibo sin insertar `planted_resources` ni grupo/outbox de monstruos, XP0 y resultado12954false. La ruta actual complete siempre inserta recurso: no reutilizarla con un booleano cambiado al final. Cancelar libera reserva sin consumir ni crear recibo de éxito; un ticket ya confirmado no puede cancelarse para recuperar semilla. Repetición consulta recibo y no vuelve a tirar.

El handler nativo de12954 consume una semilla también en fallo; evitar segundo decremento enviado por otro carrier. Cotejar contexto y cálculo visual nativo antes de fijar tramos DB: una política arbitraria no será visualmente coherente por enviar simplemente el porcentaje en un campo inventado. El perfil de auditoría con OpenPlanting limita la validación visual; no se modifica cliente ni se declara resuelta esa parte.

## Pruebas que faltan

RNG fijado en0, chance−1 y chance para probabilidades0/1/2500/5000/7500/10000; cancelación antes/después de completar; fallo con último item y stack; reintento tras commit sin ACK; XP exclusivamente en éxito; ninguna creación de recurso en fallo. Probar diferentes semillas vegetales y animales: Cardo es solo un ejemplo. Estos casos especifican la futura implementación, no tests ejecutados.
