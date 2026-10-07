# Pruebas y aceptación — 26

## Base existente

- [test_haven_bag_store.py](../../../server/tests/test_haven_bag_store.py): incluido en la ejecución de base registrada.
- [test_haven_bag.py](../../../server/tests/test_haven_bag.py): incluido en la ejecución de base registrada.
- [test_inventory_move.py](../../../server/tests/test_inventory_move.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_haven_bag_store test_haven_bag test_inventory_move -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Inserción | UIDgemapropia, ranura compatible, mismo merkasaco | Consume una unidad y persiste UID de sala | Automatizada en servicio; branch de dispatcher fuente |
| Stack 3 | Instalar una de tres | Resto 2, UID unitario separado, orden de deltas + 12234 | Automatizada en servicio; falta cliente |
| Retirada llena/ocupada | Destino sin capacidad o slot ya usado | Rechazo transaccional sin perder gema | Parcial; slot ocupado cubierto |
| Selector | Retirar gema primaria/secundaria | 13090 conserva selector; 12451 misma ranura lógica | Automatizada en servicio; falta cliente |
| Propiedades | Elementos y ProtoShard persistidos | Regresan al inventario sin reroll ni pérdida | Automatizada |
| Reconnect | Cerrar Store y volver a abrir | Layout y UID durable | Automatizada para flujo DB |
| Sala ocupada | Muebles/plantas/visitantes en sala | No se destruyen objetos ni contenidos | Pendiente; no se borra ningún objeto del sistema actual |

`local_game_server.py` ya enruta 12177/13090 en esta fuente, limitado al dueño actual de su instancia 9 y fuera de combate. La aceptación visual y el gate de imagen no se han hecho. `!item 4263 3` es el comando local existente para preparar un stack de merkagema decorativa (si la consola de prueba está habilitada); 4263 y máximo99 están en el catálogo local de pilas. No representa un premio ni un costo de kamas. El costo verificado de esta operación es la propia unidad de merkagema.

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Una UID está en inventario o slot, nunca ambos; retirada no elimina contenido ni concede gema nueva.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.

## Prueba manual completa — imagen78e8ae29

Usa Adael o Audiluna, fuera de combate, y deja tres casillas libres. Esta prueba no requiere borrar personajes ni consultar UIDs.

1. En chat general escribe `!item 4263 3`. **Esperado:** recibes tres merkagemas decorativas. Anota el total si ya tenías algunas.
2. Entra en tu propio merkasaco y abre el panel de gestión de merkagemas. Elige una sala vacía y coloca una gema decorativa como primaria. **Esperado:** la pila baja en una unidad y la sala muestra la gema.
3. Coloca otra de la misma pila como secundaria en esa sala. **Esperado:** baja otra unidad, quedan dos gemas instaladas y una de las tres nuevas en inventario.
4. Sal del merkasaco y vuelve a entrar. Después vuelve al selector y entra con el mismo personaje. **Esperado:** ambas gemas siguen instaladas y las cantidades no cambian.
5. Retira primero la secundaria a una casilla vacía del inventario. **Esperado:** desaparece solo esa gema del panel y recuperas una unidad.
6. Retira la primaria a otra casilla vacía. **Esperado:** la sala queda sin las dos gemas instaladas y recuperas el total inicial más las tres recibidas. Las unidades pueden quedar en pilas separadas.
7. Sal, vuelve al selector y entra de nuevo. **Esperado:** las gemas siguen en inventario; puedes entrar al merkasaco y repetir una inserción/retirada sin duplicarlas.

El comportamiento durante combate, reintentos de paquetes, permisos ajenos, destino ocupado, rollback y preservación de propiedades se verifica automáticamente. No necesitas repetir fabricación ni las pruebas anteriores de XP.
