# Etapas y acciones verificadas contra datos nativos

## Fallo concreto del crecimiento

`PlantingRuntime.mature` consulta exclusivamente `stage=1` y cambia la planta a 2 si esa etapa existe. En ejecuciones posteriores, el recurso ya no entra en la consulta. No hay transición 2→3 ni 3→4. No es un problema de esperar más tiempo: el recurso queda fuera del mecanismo.

## Cardo como caso de control

La extracción ejecutada de los datos instalados para la referencia 60 devuelve lo siguiente. La semilla es 4275 y la profesión 72. [Resultado completo del probe](probe-etapas-nativas.json).

| Etapa | Acciones nativas | Producto de referencia |
| --- | --- | --- |
| 1 | 329 | Ninguno (0) |
| 2 | 201 | 2504 |
| 3 | 203 y 100 | 2504 y semilla 4275 |
| 4 | 1475 | 11447 |
| 16 | Ninguna | Ninguno |

Los datos de las acciones indican duración 3000 ms; **esa duración no demuestra un tiempo de crecimiento**. El estado 16 no debe tratarse como una etapa final cosechable: no tiene acciones y `bOm.bcP()` devuelve falso para ese estado. Otros parámetros permanecen identificados por su getter nativo en el JSON; no se les atribuye significado de XP o rendimiento sin seguir sus consumidores.

## Solución del servidor que debe implementarse

Sustituir el salto fijo 1→2 por transiciones explícitas por referencia y etapa, con vencimiento persistido y tiempos constantes configurables, como pidió el usuario. No ordenar todos los números de etapa y asumir que son etapas sucesivas: estados especiales y variantes raras requieren reglas distintas. La misma tabla debe resolver las acciones válidas para recolección; la acción que existe en etapa 3 puede no existir en etapa 2.

Añadir casos para árboles, incluyendo fresnos, y otras plantas. Al reiniciar, procesar cada vencimiento una sola vez y publicar el estado correspondiente sin cambiar `ownerAccount` a una fecha. Debe funcionar también al descargar y recargar la zona, siguiendo la política de zonas ocupadas del documento general.

## Límites de la comprobación

Se ejecutó extracción nativa y se inspeccionó el scheduler; no se implementaron transiciones ni se afirma una prueba gráfica de crecimiento completo. Falta determinar reglas nativas de las variantes especiales y completar el inventario de transiciones de las demás especies; son tareas técnicas del auditor, no decisiones pendientes del usuario.
