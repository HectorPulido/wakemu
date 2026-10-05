# Información pendiente — 2

## Pendientes específicos

| ID | Dato o decisión | Cómo resolverlo | Impacto |
| --- | --- | --- | --- |
| 1 | Referencias concretas bebé/adulto y reglas por familia verificadas. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 2 | Tiempo de maduración, HP al crecer y política de especies sin adulto. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 3 | Mensaje nativo para cambiar forma y componentes sin perder identidad. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |

1. en server/protocol/monsters.json, revisar el family id, y revisar si hay algun is_boss
Ejemplo, la familia 68 es la familia de los jalatos, al plantar debe salir un jalatin que son los monstruos de nivel mas bajo, y deben crecer a jalato que es el siguiente escalon (revisa por nivel), luego a jalato de guerra, este es un proceso no determinista, es decir el jalato se puede quedar como jalato y cada escalon es mas dificil de subir que el anterior. Importante darle al jefe de mazmorra MUY poca posibilidad, por ejemplo el jalato real, que solo salga uno de cada muchisimas veces.

2. Tiempos de maduracion constante, configurable, pero que cada monstruo tenga una posibilidad de subir de tipo aleatoria, y que vaya bajando a medida de que suba el nivel.
3. Revisa si eso existe, si no, hay que eliminar el mob y cambiarlo de tipo

Importante: este proceso solo ocurre si hay gente en el mapa

## Reglas para completar la especificación

No inventar fórmulas oficiales, opcodes, flags o carriers. Para una regla configurable, fijar rango, default, redondeo, límites y versión. Para mensajes, demostrar encoder/decoder con fixture y consumidor nativo; no publicar archivos propietarios. Para una política de producto, documentar la elección antes de escribir tests que la congelen.

Los pasos que dependen de estos datos siguen siendo propuestas. Se puede avanzar en medición y pruebas de regresión de piezas confirmadas sin declarar cerrado el recorrido. Actualizar el cotejo si cambia la implementación concurrente.
