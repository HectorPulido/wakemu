# Prueba manual completa: Cardo desde semilla hasta cosecha

Esta es una aceptación propuesta para un perfil local de QA con acceso a los comandos de desarrollo. Los comandos no son comandos oficiales del juego. La ubicación y las celdas salen del test PostgreSQL `server/tests/test_flora_planting_harvest_e2e.py`, que usa geometría y autorización normal de plantación; antes de una sesión de usuario, comprobar que el mapa 235 está disponible y que las celdas están libres.

## Preparación

Con el personaje de prueba y fuera de combate/merkasaco:

```text
!tp 235 86 -161 25
!pos
!item 4275 5
```

`!pos` debe confirmar mapa235, instancia0, posición `(86,-161,25)`. La casilla objetivo `(85,-161,25)` es la casilla nativa de Cardo usada por el test de ciclo y está a una arista del personaje. `4275` es Semilla de cardo; no se debe alterar ninguna probabilidad global ni las reglas meteorológicas para hacer la prueba.

## Ciclo normal

1. Abre el inventario y usa una Semilla de cardo con el control nativo de usar objeto. Si el cliente entra en modo de plantación, selecciona la casilla objetivo `(85,-161,25)` y completa la acción. El personaje debe gastar una semilla; si la tirada falla, no debe aparecer un recurso y el recibo debe registrar el resultado. Reintenta con otra semilla solo después de confirmar el resultado fallido.
2. Al aceptar la plantación, verifica que el Cardo aparece en la casilla, reabre/reentra al mapa y comprueba que conserva su etapa e identidad.
3. Espera los plazos de crecimiento configurados localmente (30 segundos por arista para Cardo60 en la política actual). En etapa3 normal, comprueba que aparecen las acciones nativas `100` (obtener Semilla de cardo) y `203` (Cardo borriquero normal, item2504). El test automatizado usa primero la acción100: debe devolver una semilla y regresar la planta a etapa2; al crecer de nuevo a etapa3, cosecha con la acción203.
4. La cosecha normal debe dar el producto2504 y retirar ese recurso del mapa. Tras salir y volver a entrar, la casilla debe seguir libre; si se replanta allí, debe ser un recurso con UID nuevo.

## Rama rara opcional

La política local actual asigna probabilidad `0.01` a la transición opcional Cardo etapa3→4. Si esa tirada ocurre durante la prueba, el resultado esperado es Cardo tornasolado en etapa4, con la acción nativa `1475` y producto11447. Cosecharlo debe retirar el recurso. La variante es una rama aleatoria y no es requisito para que el Cardo normal esté maduro/cosechable en etapa3. No se fuerzan probabilidades para provocar esta rama.

## Evidencia que se debe guardar

- `!pos` antes de plantar y confirmación del mapa/casilla;
- semilla antes y después del intento, y mensaje de ocupación/resultado;
- etapa visible después de cada transición y lista de acciones de cosecha;
- producto y XP de Herbolario en la rama normal (o producto de variante en etapa4);
- reentrada y verificación de retirada/replantación con identidad nueva.

Marcar por separado los resultados aleatorios de la plantación y de la variante. Un paquete optimista, una semilla consumida o una captura de un recurso preparado por SQL no demuestran plantación nativa exitosa.
