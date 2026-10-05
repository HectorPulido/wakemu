# Solución propuesta — E10

Garantizar que creación/actualización de una hoja de equipo registre índices nuevos sin perder existentes.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Fijar entrada mínima del defecto

Guardar fixture con equipment set solo 0 y hoja nueva índice 2. Comparar tags/índices antes/después y usar parser nativo. Diferenciar envelope set frente a registry bootstrap y ACKsave: cada carrier tiene reglas propias.

## 2. Comprobar merge nativo

Revisar handler que recibe set completo/parcial y si reemplaza o inserta. No asumir que repetir índice 2 en payload equivocado lo registra; identificar refresh deopenpanel y owner registry. Una colección sin entrada no es una hoja vacía.

## 3. Generar conjunto canónico

Resolver todos los índices disponibles y hojas completas; al añadir índice ausente incluirlo una vez. Conservar índices existentes y campos válidos sin duplicación de tags. Si se envía delta, probar carrier propio de add y no usar updateonly.

## 4. Mantener atomicidad de creación

Save/create valida y persiste antes de construir gear/apt/deck/sheet ACK. Todos los registros deben descubrir índice nuevo en la misma revisión. Fail parcial no anuncia build inexistente; rechazo restaura conjunto previo.

## 5. Validar UI y replay

Crear hoja nueva en vivo, seleccionar equipo y comprobar que no produce jFr nulo. Reconnect debe mostrar mismo conjunto. Delete/recreate y mensajes repetidos no duplican registros ni vuelven a hoja anterior.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Una build nueva anunciada tiene una entrada de equipo registrable, no un update dirigido a un índice inexistente.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
