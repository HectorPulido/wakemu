# Eventos externos 1001 y1028: auditoría del productor

La inspección offline revisó todas las178.337 definiciones instaladas aNw:
`apw.a(aNw) → bcA.AH → eVn.aZO`. Ninguna emite1001 ni1028. La ausencia de
emisor de efecto no prueba que el servidor original no produzca esos eventos.
Resultado y hashes: `server/protocol/native-lifecycle-event-producers.json`.
Reproducción: `FindNativeLifecycleEventSources.java` y
`FindNativeEventConstant.java` (bytecode completo de wakfu-client.jar).

`eFl.<clinit>` incluye1028,1003,1001,1005,1002 en su BitSet. `eFl.d` sólo
comprueba intersección para la semántica de reset en el motor. `eFK.pyl`
clasifica los eventos externos. Ninguno acredita una fase del combate ni un
productor. El scanner no encuentra llamadas de Qf con esos enteros.

Los otros literales son espacios diferentes:1001 en `bka.a(QM)` compara el
ID de una notificación `ffG` de retirada de efecto para actualizar interfaz;
1028 en `bQY` es `FIGHT_JOIN_ERROR_CANT_STAKE`, y OpenGL usa ese valor aparte.
No deben transformarse en triggers de combate.

El caso funcional concreto es la innata Xelor6755: el grupo313103330 se
suscribe a máscara5/[1028], flags17. Sus hijos313107,313108,349284 otorgan
hechizos mediante649 cuando no hay acción933 y GetInstanceId()!=862. La
inicialización anterior que sólo entregaba1003 dejaba el registro de grants vacío:
este resultado no se corrige ejecutando esos hijos saltándose el evento.

El camino genérico de registro→ejecución→coste/rango→retirada está probado
por separado para649. En la auditoría original faltaba delimitar el origen,
momento, canales y managers destinatarios de1028/1001: un productor nativo
adicional o una captura oficial ya guardada con el cambio de estado y sus
mensajes puede delimitar esa relación. No se hicieron peticiones oficiales
ni se añadieron triggers por intuición en esta auditoría.

## Política de apertura 1028 (implementación en validación, 5 de octubre)

La descripción instalada `content.33.343565` sitúa expresamente la conversión
de la mitad de PW a puntos de Stasis y los grants secundarios del Steamer al
comienzo del combate. El árbol original de la innata7675 suscribe343565 a
1028; Ouginak7521 y Xelor6755 usan ese mismo evento para sus grants. Se
implementa una frontera de apertura de clase antes de la reacción general
1003, con fuente nula y selección nativa en canales6/60/61. Sólo se envía1028
a managers controlados con raíces de clase instaladas; no se inventa una
inicialización de clase para NPC. El orden y el productor son política del
servidor emulado, no un callsite demostrado del cliente.

Los registros ya enlazados pueden ejecutar grupos cuyo So(2) no sea0/1:
eYg.bbA compara exactamente con1 y su rama de hijos usa bbA. El valor10 del
grupo999/327548 tiene bbA=false y bbB=false; la selección fresca sigue
rechazada por esa combinación, pero el listener estatal conserva su enlace.
El decodificador de ejecución ya no confunde esta comparación con un enum.

Las primeras pruebas de apertura revierten correctamente ante el siguiente
criterio no soportado: inventario y fechas promocionales de4464. No se
omiten esas condiciones para declarar funcional el recurso o los grants.
Los resultados positivos y el consumo se documentarán tras superar esa
frontera. No se emitió1037 como regeneración de turno: la descripción
original lo relaciona con ataques de la torreta, una causa diferente.


## Corrección de fases1001/1002 (2026-10-05)

La interpretación anterior de1001 como fin de turno queda retirada. La
localización española original de los efectos197715 (Sacrógrito) y339741
(Uginak) dice «Al principio del turno», y sus máscaras5 contienen1001. Los
efectos343079 (Stasis del Steamer),339766 (liberación de presa) y418649 dicen
fin de turno y sus máscaras contienen1002. El tooltip general del estado4121
no acreditaba la fase del hijo413768: este hijo1001 selecciona400 o retira el
modo mediante321; no ejecuta la pérdida de BC anunciada por el tooltip.

La política del servidor emulado entrega1001 al inicio y1002 al final,
separadamente. Inicio sucede después de la única expiración de inicio ya
existente; fin sucede antes de la única expiración de fin. Se conserva fuente
nula, canales6/60 del actor activo y61 de los managers registrados, y prioridad
y filtros Qf. Esta colocación de productores es inferencia de servidor apoyada
en descripciones y listeners nativos; no se afirma un callsite productor del
cliente. Nunca se fusionan los bitsets de ambas fases ni se emite1037 genérico.

Los markers persistidos usan turno/actor/fase. ACK y recuperación anuncian el
turno existente sin volver a producir sus reacciones. El helper de inicio usa
un único preview y factory para1001 y callbacks Qs opcionales: una excepción
revierte ambos. Las pruebas previas de Sacrógrito/Hupper se reasignan a inicio;
probar sus hijos a fin no acreditaba la fase correcta.


### Ciclo original de Stasis y propiedad del contenedor

El estado7647 tiene máximo3. En1002,343080 (familia40) consume tantosSP como
su nivel actual. El hijo395904 (304) reaplica7647 con +1 nivel si el estado
sigue presente. Con3SP iniciales el ciclo es3→2 (estado nivel1→2) y después
2→0 (retirada del estado), no un consumo plano1 en todos los turnos.

Reaplicar un estado desde un listener puede registrar nuevamente el mismoPK
sobre su nuevo carrier. Qa.aZN difiere la ejecución de esa suscripción; por
ello hay una API de registro validado independiente del ancestry de ejecución
inmediata. La protección contra recursión inmediata permanece intacta.

Asimismo, el clonQf conserva suPL/fyW mientras ejecuta todos los hijos, aunque
un hijo321 retire el estado del ledger. El replay usa el scope de contenedor
ya acreditado durante toda la activación y conserva el payloadrHA sólo hasta
salir de ese scope. No se revive el estado, no se conserva un UID inexistente
para eventos futuros y no se deriva su identidad de baseUID. Esta propiedad
permite evaluar los hermanos restantes después de la retirada nativa.
