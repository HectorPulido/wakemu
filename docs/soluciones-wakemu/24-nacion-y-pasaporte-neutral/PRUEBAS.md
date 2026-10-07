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
| Personaje nuevo | Perfil limpio y DB temporal | El serializador emite `NATION_ID=0` y `PASSEPORT_INFO=00` | Automático: cubierto por los serializers; visual aún no probado |
| Pasaporte | `/passport` abre `passportDialog` | `pvpLadderEntry.nationId == 0` y texto Neutral | Binding nativo cotejado; aceptación visual pendiente |
| Mapa nacional | Entrar a región asociada a Amakna | Sin alineamiento territorial activo según requisito | Pendiente: no hay autoridad mapa→nación verificada en los catálogos inspeccionados |
| Otra región | Cambiar a otra región | No cambia la ciudadanía del personaje ni hereda nación ajena | Pendiente de aceptación visual; contexto territorial sigue separado |
| Reconnect | Recargar las pantallas | No reaparece estado de pasaporte de la plantilla | Prueba de serializador PASS; aceptación visual pendiente |
| Carriers propios | Cotejar formatos 5/10/11, `PASSEPORT_INFO` y sincronización 15984 | Nación0, pasaporte `00`, sincronización nacional vacía sin alterar campos vecinos | 39 pruebas wire/social OK; incluye fixtures sintéticas, no aceptación visual |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Ni personaje ni lugar reciben alineamiento de otra cuenta o captura; neutralidad es explícita y consistente.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.


## Gate actualizado — 7 de octubre

En el entorno local de verificación, `PYTHONPATH=server:server/tests .runtime/local/verification-venv/bin/python -m unittest test_wire test_social -q`: **39 pruebas OK**. Incluye la regresión nueva de `PASSEPORT_INFO`: un byte de plantilla no-default se sustituye por `00`, conservando los bytes vecinos. Son pruebas de serialización, no una observación visual de `/passport` ni una prueba de ownership territorial. El roster qZ, el modelo nativo del pasaporte y el locale están cotejados por separado en [REVISION-RESPUESTAS.md](REVISION-RESPUESTAS.md).
