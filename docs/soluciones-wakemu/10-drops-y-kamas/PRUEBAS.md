# Pruebas y aceptación — 10

## Base existente

- [test_combat_rewards.py](../../../server/tests/test_combat_rewards.py): incluido en la ejecución de base registrada.
- [test_inventory_uids.py](../../../server/tests/test_inventory_uids.py): referencia existente; no ejecutado en el lote de base registrado.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_combat_rewards test_inventory_uids -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Victoria con tabla | RNG fijo para uno y cero drops | Lista exacta del recibo | Pendiente de implementar/verificar |
| Probabilidad saturada | Multiplicador lleva p>1 | Clamp documentado, no drops infinitos | Pendiente de implementar/verificar |
| Inventario lleno | No hay slot para premio | Entrega pendiente durable o regla explícita, sin pérdida | Pendiente de implementar/verificar |
| Wallet cerca de límite | Kamas grandes | Rechazo/clamp según contrato sin overflow | Pendiente de implementar/verificar |
| Resultado duplicado | Repetir premio de mismo fight | Sin nuevos UIDs ni kamas | Pendiente de implementar/verificar |
| Corte tras commit | Recovery antes de respuesta | Resumen e inventario mismo premio | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Resumen=recibo=wallet/inventario; cada UID otorgado y cada kama se entregan una vez.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.

## Aceptación visual Adael — 7 de octubre

Dos victorias: +38/+30kamas, inventario131→161 y objeto12325 pila3→6. RecibosSQL coinciden; account_wallets es por cuenta, compartido con Audiluna/Npers. Persistencia manual tras reinicios pendiente.

### Diferencia inicial de siete kamas explicada

El recibo de intercambio13 (2026-10-07T03:15:36Z) conserva balances account2=93/account5=107. Adael pertenece a account2; sus victorias12/13 conceden38/30. Wallet161=93+38+30. No acredita pérdida de recompensa ni un saldo inicial100 por personaje; esquema003 define monedero por cuenta, default0.

## Gate de ampliación candidato

Imagen b33fe0e4046c047b7cba323d33737527e15d22b2d4db9bd09124db0bd9ae4b30:75/75 pruebas ejecutadas desde /app con módulos de imagen y tests montados readonly. Fuente añade caso integrado real reward/drops/delivery:62/62, cubre bolsa+temporal, rollback y reintento. Hashes de todos los módulos existentes de combate coinciden entre candidata y activa d990b252. Candidata no desplegada en world; smoke socket aislado aprobado:TLS, colocación, puño, victoria,12925 y reconexión con XP/kamas/botín/overflow durables.

## Preparación manual de inventario lleno

Adael en selector, sesión SQL sin personaje:32 objetos2021×1 insertados solo en huecos. Bolsillos30/30 y bolso4/4; pila original12325×6 intacta. Drop temporal×4 (versión2,40000bp); restaurar versión1 al concluir. Usuario autorizado a probar overflow/reclamación.

## Fallos detectados por aceptación UI Adael

Inventario lleno muestra En espera y conserva recompensas. Arrastrar13993 rechazado por Requested amount exceeds temporary quantity; Obtenerlo todo12294 rechazado por Invalid12294 request fields. Cerrar12561 bodyvacío no tiene handler y se recarga al reconectar. UI agrupa filas por referencia/cantidad pero reentrada muestra filas separadas: investigar UID/cantidad canónicos. El harness previo usaba peticiones construidas y no demostraba estos carriers reales. Drop temporal×4 restaurado a×1 tras reproducir el fallo; no se borró botín.

### Cotejo de supuesta duplicación

SQL temporal Adael:9748×3,11516×2,12513×4,12518×2,12519×2,18686×2,18687×3;18 unidades/7referencias/18UIDs. SUM(fight_drop_delivery_receipts.temporary_quantity) coincide por referencia y no existen temporary_inventory_transfer_receipts de Adael. Captura inicial muestra7pilas agrupadas; reentrada18filas separadas. No hay duplicacióndurable ni transferencia confirmada; es incoherencia de agrupación/publicación del cliente.12294 GetAll source==destination rechazado indebidamente;13993 cantidadagrupada>filaUID provoca rechazo. Corregir autoridad/snapshot antes repetiraceptación.

## Candidata de corrección UI completa

Imagen2d77ad4525d4b2afeacc86fca3dc95fc1a2f8595b0c3fa2e9431c38c414033f1:160/160 tests de imagen aprobados en DBaislada. Incluye12294 mismo personaje,13993 agrupado/merge,12561 cierre durable,13447 reciclaje temporal y12890 contadorunidades; migraciones001–048 continuas. Incluye borrado046 y soloDDL045 ajena necesaria por prefijo, con funciónIA idéntica al live. Aún sin despliegue; pendiente smoke socket con los carriers UI reales corregidos.

## Despliegue merge7octubre

Imagen9af0658c (wakfu-local-world:merged-verified) desplegada healthy, PostgreSQL001–048. Gate de imagen200/200; socket de recuperación agrupada, GetAll propio, reciclado, abandono y reconexión aprobado; borrado socket validado en candidata equivalente. IA y todos los módulos de combate conservados desdee18verified. Respaldo privado pre-inventory-merge-20261007.dump. Confirmación manual UI recibida: usuario declara «Todo funciona bien» tras la prueba general.

## Resultado manual del usuario

Con Adael, al entrar todavía había el último botín en espera; al pulsarlo recibió los objetos. Confirmó «Todo funciona bien» para la prueba completa enviada (liberar espacio, arrastrar, Obtenerlo todo, reentrada, reciclaje, abandono, victoria Mimic y persistencia). Captura posterior: bolsillos23/30, Dulzura próspera21, otros premios recuperados4/2/2/3/2/2/3 y489kamas. No se atribuye esta aceptación a condiciones especiales de drops no ejercitadas por esa prueba.
