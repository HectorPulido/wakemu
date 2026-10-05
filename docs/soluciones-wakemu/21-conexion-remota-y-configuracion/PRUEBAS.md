# Pruebas y aceptación — 21

## Base existente



El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest  -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Localdefault | Bind/anuncio local coherentes | Todos endpoints alcanzables en perfil existente | Pendiente de implementar/verificar |
| Remoto | Host real y ports anunciados | Dispatcher/world/API coherentes desde otro equipo | Pendiente de implementar/verificar |
| Bind 0.0.0.0 | Proceso escucha todas interfaces permitidas | No se anuncia 0.0.0.0 como destino | Pendiente de implementar/verificar |
| Anónimo API | Request externo/testcommand | RechazoE03, sin acción | Pendiente de implementar/verificar |
| Secretos | Revisar config/log/distribución | Sin tokens ni assets/client versionados | Pendiente de implementar/verificar |
| Rollback | Revertir config en entorno autorizado | Endpoints anteriores recuperados, datos intactos | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Bind y anuncio son distintos; acceso de red nunca reemplaza autenticación ni autoriza publicar assets del cliente.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
