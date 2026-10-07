# Prueba completa de Wakfu/Stasis

Versión ecológica desplegada: imagen3540c61b, SQL034, 246 pruebas automáticas OK. Aceptación visual pendiente. Esta prueba usa Audiluna en la zona de cultivo de Zurkalia donde ya plantaste cardos; prueba recursos recién plantados, porque los anteriores pueden conservar variantes raras.

## Plantas, árboles y campos

1. Anota el porcentaje y lado actuales del indicador Wakfu/Stasis al pasar el ratón.
2. Escribe en General, uno por uno:

   ```text
   !item 4275 1
   !item 8063 1
   !item 1752 1
   ```

   Debes recibir una semilla de cardo, un esqueje de fresno y una semilla de trigo. La cantidad debe actualizarse sin reconectar.
3. Planta cada recurso en una casilla válida de terreno. Para esta aceptación, la política de arraigo está temporalmente en100%; no cambia las variantes de crecimiento. Debe consumirse una unidad y aparecer un mensaje de Información con familia/región, población antes/después, rango de equilibrio y cambio real de afinidad.
4. El mensaje debe indicar +0,25 puntos porcentuales si la acción acerca la población al equilibrio, −0,25 si la aleja y0 si no cambia la distancia al rango. En el límite99% puede haber saturación. El indicador redondea visualmente; una acción de0,25 no tiene por qué cambiar un entero visible. No debe saltar decenas de puntos.
5. Espera90 segundos después de plantar el último recurso. Los nuevos cardos y fresnos deben presentar la variante normal, con extracción de semillas/esquejes y retirada disponibles. El trigo conserva una probabilidad rara del1%; si aparece una variante especial, anota cuál, sin confundirla con un fallo del mensaje ecológico.
6. Extrae una semilla del cardo, un esqueje del fresno y semillas del trigo normal. Debe entregarse el producto, conservarse la planta/árbol/cultivo y emitirse Información con población sin cambios y afinidad sin cambios. Si la acción reduce la etapa de crecimiento, espera a que vuelva a madurar antes de continuar.
7. Retira los tres recursos nuevos usando su acción destructiva (cortar/talar/cosechar, según el menú). Cada retirada debe entregar su producto y quitar el recurso del mundo; Información debe mostrar población reducida y el cambio conforme a su distancia al equilibrio. Retirar no siempre da Stasis: si corrige un exceso, puede dar Wakfu. Recolectar semillas no debe cambiar afinidad.
8. Cambia de personaje y vuelve a Audiluna. Productos, recursos retirados y afinidad deben mantenerse, sin repetir mensajes/recompensas por reconectar.

## Monstruos

9. En General escribe:

   ```text
   !item 7358 1
   ```

   Debes recibir una semilla de Tofu.
10. Plántala en una casilla válida y aléjate de esa casilla. Debe consumir una semilla y explicar en Información que todavía no hay un monstruo vivo ni cambio de afinidad.
11. Espera60 segundos. Debe nacer un miembro de la familia Tofu y aparecer Información de su población/rango y cambio de afinidad. Dentro del rango de equilibrio es correcto que el cambio sea0. La afinidad se evalúa al nacimiento, sin premiar también la colocación de la semilla.
12. Extrae semillas del monstruo. Debe aumentar el stack correspondiente y explicar que la población y afinidad no cambian; el cooldown ya comprobado debe seguir funcionando.
13. Ataca ese monstruo, inicia el combate y derrótalo con Fulgor o un ataque que ya tengas disponible. Al terminar debe regresar la interfaz de exploración. Información debe mostrar su retirada de población y el cambio ecológico correspondiente, sin duplicar la recompensa.
14. Cambia de personaje y vuelve. El monstruo derrotado no debe reaparecer; afinidad y productos deben conservarse.

Si tienes un segundo cliente abierto, comprueba además que solo Audiluna recibe sus mensajes ecológicos de Información. Esta prueba no modifica hechizos ni requiere probar hechizos de monstruos.
