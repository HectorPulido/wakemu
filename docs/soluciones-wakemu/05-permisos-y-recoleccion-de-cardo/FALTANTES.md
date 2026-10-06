# Información pendiente — 5

## Pendientes específicos

| ID | Dato o decisión | Cómo resolverlo | Impacto |
| --- | --- | --- | --- |
| 1 | Correlacionar la solicitud real reportada con una acción concreta del Cardo, con captura autenticada. | Captura dirigida del 12995 y del recurso/etapa objetivo | Impide certificar el recorrido gráfico de ese caso; el catálogo nativo ya enumera las acciones por etapa |
| 2 | Política de recursos públicos/propios y significado de campos a cero. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 3 | Codec/resultado de ocupación de cosecha vegetal y transición de recurso aceptados por el servidor. | Correlacionar 12230, resultado del cliente y cambio nativo del recurso | Impide cerrar el ciclo de cosecha |
| 4 | Cantidad/probabilidad de productos y fórmula de XP por acción. | Consumidor nativo o captura correlacionada; de otro modo, política local explícita | Impide otorgar recompensas sin inventar reglas |

1. Debes hacer esto en un cliente, yo reproduje el error pero es mejor que tu captures todo
2. No hay tal politica por ahora
3. Revisa Java y el codigo del servidor

Las acciones de flora ya están exportadas, por recurso y etapa, en `server/protocol/plant-resources.json`. Esa exportación identifica profesiones/niveles, duración y referencias de productos; no resuelve la cantidad/probabilidad ni la respuesta completa del servidor.

## Reglas para completar la especificación

No inventar fórmulas oficiales, opcodes, flags o carriers. Para una regla configurable, fijar rango, default, redondeo, límites y versión. Para mensajes, demostrar encoder/decoder con fixture y consumidor nativo; no publicar archivos propietarios. Para una política de producto, documentar la elección antes de escribir tests que la congelen.

Los pasos que dependen de estos datos siguen siendo propuestas. Se puede avanzar en medición y pruebas de regresión de piezas confirmadas sin declarar cerrado el recorrido. Actualizar el cotejo si cambia la implementación concurrente.
