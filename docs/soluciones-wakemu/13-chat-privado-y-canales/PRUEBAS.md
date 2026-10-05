# Pruebas y aceptación — 13

## Base existente

- [test_social.py](../../../server/tests/test_social.py): incluido en la ejecución de base registrada.
- [test_chat_console.py](../../../server/tests/test_chat_console.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_social test_chat_console -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Privado A→B | C cercano escucha | Solo B y ecoA según contrato | Pendiente de implementar/verificar |
| Local | B misma instancia/C distinta | Solo alcance definido | Pendiente de implementar/verificar |
| Grupo | A/B en party,C fuera | C no recibe | Pendiente de implementar/verificar |
| No conectado | Nombre válido sin sesión | Error preciso, no broadcast | Pendiente de implementar/verificar |
| Nombre normalizado | Mayúsculas/acentos según nombres permitidos | Destino inequívoco y sin colisión | Pendiente de implementar/verificar |
| Comando no admin | Normal manda ! por canales | Rechazo 32 sin ejecutar ni revelar datos | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Un privado nunca usa broadcast; solo destinatarios autorizados reciben el contenido.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
