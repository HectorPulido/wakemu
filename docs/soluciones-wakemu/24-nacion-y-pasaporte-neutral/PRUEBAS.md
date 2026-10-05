# Pruebas y aceptación — 24

## Base existente

- [test_creation.py](../../../server/tests/test_creation.py): referencia existente; no ejecutado en el lote de base registrado.
- [test_inventory.py](../../../server/tests/test_inventory.py): referencia existente; no ejecutado en el lote de base registrado.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_creation test_inventory -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Personaje nuevo | Perfil limpio y DBtemporal | Nación/pasaporte neutral coherentes | Pendiente de implementar/verificar |
| Mapa nacional | Entrar a región del catálogo de Amakna | Sin alineamiento territorial activo según requisito | Pendiente de implementar/verificar |
| Otra región | Cambiar a región de otra nación | No valor heredado diferenciado accidentalmente | Pendiente de implementar/verificar |
| Ítem pasaporte | Si realmente existe instancia inicial | Origen/propiedad correcto, no borrado ciego | Pendiente de implementar/verificar |
| Reconnect | Recargar todas las pantallas | No vuelve nationcapturada | Pendiente de implementar/verificar |
| Legacy | Migrar copia con ciudadanía legítima | Política explícita preserva datos necesarios | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Ni personaje ni lugar reciben alineamiento de otra cuenta o captura; neutralidad es explícita y consistente.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
