# Información pendiente — 4

## Pendientes específicos

| ID | Dato o decisión | Cómo resolverlo | Impacto |
| --- | --- | --- | --- |
| 1 | Fórmula de probabilidad, escala y redondeo de esta versión. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 2 | Campos del contexto nativo y efecto del override en el perfil del usuario. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 3 | Consumo de semilla y XP cuando falla la tirada. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |

1. La probabilidad si no estoy mal depende del nivel del peletero/herbolario/leñador, va desde 1%, 25%, 50%, 75% y 100%
2. N/A, es importante no modificar el cliente
3. Si falla no hay xp y se consume la semilla, si lo logra, hay xp y se consume la semilla, si se cancela no hay xp ni se consume.

Importante: Para la formula, inventemos algo, plantar debe dar poca xp, recolectar un poco mas, craftear depende del numero de casillas de la receta, y todo modificable desde la db

## Reglas para completar la especificación

No inventar fórmulas oficiales, opcodes, flags o carriers. Para una regla configurable, fijar rango, default, redondeo, límites y versión. Para mensajes, demostrar encoder/decoder con fixture y consumidor nativo; no publicar archivos propietarios. Para una política de producto, documentar la elección antes de escribir tests que la congelen.

Los pasos que dependen de estos datos siguen siendo propuestas. Se puede avanzar en medición y pruebas de regresión de piezas confirmadas sin declarar cerrado el recorrido. Actualizar el cotejo si cambia la implementación concurrente.
