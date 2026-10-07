# Pruebas y aceptación — 16

## Pruebas de espectador ejecutadas

```sh
PYTHONPATH=server python3 -m unittest server.tests.test_combat_spectators -v
```

Resultado: **9/9 pasaron**. Verifican el decoder/encoder `cva/12044`, layout heredado `cvb/12847`, payload `feN`, snapshot actual al entrar, solo eventos posteriores, reentrada que limpia batches anteriores al snapshot, suscripción aislada de participantes, fencing por lease/mapa/instancia, cleanup por salida/desconexión/cierre y límites para observadores lentos.

El verificador Java independiente contra el cliente instalado acepta un fixture sintético de 143 bytes y confirma que el timeline `feN` se decodifica y vuelve a emitir byte por byte:

```sh
javac -proc:none -cp 'client/lib/wakfu-client.jar:client/lib/*' -d /tmp sniffer/java/VerifySpectatorBootstrap.java
java -cp '/tmp:client/lib/wakfu-client.jar:client/lib/*' VerifySpectatorBootstrap
```

Salida: `native cva/12044 and feN reader accepted 143-byte current-state fixture`.

Estas verificaciones son de codecs y registro en memoria; todavía no ejercitan dos clientes, el marker 13753, el dispatcher 13413/12154, el snapshot generado desde un combate real ni el retorno al mundo.

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Marcador vivo | C entra al mapa con fightA/B | Ve solo ID real actual | Pendiente: 13753 necesita escena válida |
| Entrada/salida | C envía 13413/12154 | Se conecta/desconecta de forma aislada | Codec nativo verificado; handler pendiente |
| Observar en turno | Snapshot y eventos concurrentes | Estado consistente y secuencia continua | Registro aislado probado; fanout pendiente |
| Cast espectador | C pide actuar por A | Rechazo, sin costo ni evento | Pendiente de integración TLS |
| ACK ausente | C no responde | Participantes continúan | Diseño no bloqueante probado en registro; fanout pendiente |
| Fin observado | Termina combate | C vuelve al mundo y marcador desaparece | Pendiente de integración |
| Privacidad | Fight cerrado/no visible | No snapshot ni inventario de participantes | Política de acceso pendiente |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Observar nunca concede control; un cliente lento o desconectado no bloquea el combate observado.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
