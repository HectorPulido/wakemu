# Cambio de entrega retirado: validación gráfica pendiente

El cambio a12613 descrito abajo fue retirado tras el usuario informar una regresión. El servidor volvió a13497. Las comparaciones Java de registro no prueban que la interfaz de combate funcione; no se considera resuelto Sacudido ni Concentración. Se conserva el análisis como antecedente, no como estado actual.

# Retención de estados en el cliente

El servidor aplicaba Sacudido (8913) y Concentración (3442), pero enviaba el carrier eZk310 por 13497/cvY. El manejador aTR.cbj exige aZN() o bbW() para insertar el efecto en Qf; eZk.aZN() siempre devuelve false. El paquete llegaba sin registrar el estado visible.

Se entrega únicamente el carrier310 por 12613/cvX → cjK → aVo.cYg, con eIK=false. Este camino llama Qf.p cuando Ty() es verdadero, conserva UID/baseUID, objetivo y tiempos, y desactiva gameplay con bbq(): no vuelve a ejecutar los hijos ya calculados por el servidor. Los paquetes13497 de otras familias y la retirada13560 no cambian.

Prueba original reproducible: sniffer/java/ProbeNativeStateDelivery.java decodifica los paquetes Python mediante cvX.dp y ejecuta aTR/aVo originales. Para3442 nivel15 y8913 nivel30:13497 registra0;12613 registra1, gameplay deshabilitado.

Regresiones de carrier, sustitución, retirada de hijos y decurse:31 pruebas pasan. La prueba de entrada común utiliza actorYopuka a20/200, monstruo4085 nivel23 (530HP nativos), normales/críticos de4780/4783/4778; verifica daño, supervivencia, identidad de carriers y conservación del combate original. Los normales incrementan3442;4780 aplica8913 en ambas variantes. En el fixture crítico3442 no se incrementa: queda pendiente investigar el productor/condición de Concentración crítico, separado del defecto de entrega. No se ha confirmado todavía la interfaz después del despliegue.

## Revisión posterior de la entrega revertida

`ProbeNativeStateManager.java` amplía la prueba anterior: usa `eZV` original (sin sustituir `p`), resolución `PN/PW` de los actores y ejecuta `aVo.cYb`, `cYc` y `cbj`. Los estados 3442 y 8913 permanecen en `eZV.fSs` después de la acción 12613; el recorrido 13497 no los registra. La resolución de actores es necesaria: ejecutar estos métodos sin un registro de actores provoca un falso negativo al volver a resolver las identidades del paquete.

En `snapshot-final/decoded/frames.jsonl` de la captura oficial del 3 de octubre hay 79 carriers de clase310, todos en12613 y ninguno en13497. Los sintéticos−5/−7 oficiales y−1 local tienen `actionId=-1` y `script=0` en `PH`; esa diferencia sola no acredita una causa gráfica. El encabezado12613 oficial usa `eIK=false`, igual a la propuesta anterior.

Esto prueba registro y finalización del modelo nativo. No reproduce la cola completa con OpenGL ni confirma iconos en pantalla. La entrega activa continúa siendo13497: no se cambió durante esta revisión. Cualquier nuevo ensayo debe usar un cliente propio y comprobar ejecución de cola, daño y registros después del refresco12873 antes de declarar resuelto el problema visual.

## Corrección coordinada con identidades de acción

La entrega310 vuelve a12613 con `eIK=false`, ahora junto al asignador de un ID cvB distinto por paquete. La identidad de acción de presentación no reemplaza UID/baseUID del carrier. `ProbeNativeStateQueue.java` encola el `aVo` original en `aER/aEV`, ejecuta `cbu`, comprueba que la cola se vacía y consulta el `eZV.fSs` original: 3442 y8913 siguen registrados al finalizar. No sustituye el método de registro ni la ejecución de la acción.

Validación de servidor:14 pruebas carrier/handler/retirada de hijos y la prueba de entrada común con12 variantes Yopuka más4 segundos lanzamientos de Sacudida pasan. La prueba gráfica utiliza únicamente la nueva cuenta de prueba del perfil `state-carrier-test`, personaje33; no usa la ventana del usuario. La comprobación de iconos y preservación posterior a12873 continúa pendiente hasta documentar el resultado de esa sesión.

### 2026-10-05: prueba viva y retirada de carriers

Perfil separado `state-carrier-test`, actor33 nivel20, combate494024632, enemigo nativo4085 nivel23/530HP. Celeste produjo daño530→522 y el Qf del cliente retuvo3442/10; Sacudida produjo daño posteriormente. La primera entrega12613 sí registra ahora eZk, pero la actualización dejaba simultáneamente3442 niveles10/20/30/40/50 con distintosUID. No se declara todavía icono visible ni lifecycle completo. Las lecturas8913 no son concluyentes porque ocurrieron entre turnos; la desconexión inesperada02:35:28 se preservó sin atribuir causa.

Causa demostrada de duplicados: `cvZ→cjM→aVz.cbj` exige `eZR.fMV()` antes de `Qf.q`. El carrier evaluado tiene `aZN=false`, `bbW=false`; el payload original de aplicación no activaba `rIZ`. El protobuf instalado llama a `iB` campo1 **NotifyUnapplicationForced**; `eZR.f(iB)` lo carga en `rIZ`. El retiro ahora fuerza ese campo únicamente en TimeDatas11, conservando identidad, caster, clocks y demás bytes. La aplicación conserva su payload false original. `ProbeNativeStateRemovalGate` prueba la propia `aVz.cbj`: antes no retira, después sí retira3442/8913 del eZV real. Catorce regresiones de estado pasaron; cuatro pruebas carrier incluyen preservación temporal e idempotencia. Pendiente carga coordinada y verificación visual de actualización/retirada.

### Corrección común del contenedor PL (2026-10-05)

El cliente instalado serializa el contenedor por `PL.aZY()`, no por su nivel
`cmZ()`. `fyW.aZY()` devuelve **1**. El código original `eZR.G(int,long)`
resuelve el discriminador 1 a un estado mediante Qf/fyZ; el discriminador 3
busca un área en Qs. El comentario anterior que equiparaba wire 3 con fyW era
incorrecto. `ProbeNativeStateContainerDiscriminator` ejecuta este resolver
original: para 3442 y 8913, wire 1 recupera referencia/nivel exactos, mientras
wire 3 no recupera el estado. Las capturas oficiales también contienen PL 1.

La autoridad común de retención y daño ahora entrega tipo 1 para estados;
los identificadores de condiciones conservan 3 para áreas y 1 para estados.
Los payloads ordinarios heredan los campos 9/10 desde un scope transitorio
con contenedor acreditado, incluidas llamadas anidadas y restauración al
fallar. Los payloads de suscripciones que ya escriben PL explícitamente no
lo duplican. La retirada conserva esos campos.

Esta corrección acredita resolución nativa y serialización común; **la
visibilidad gráfica sigue pendiente de validar en un cliente actualizado**.
La familia 400 requiere además comprobar su entrega 12613: los grupos 330
oficiales usan 13497, por lo que no se cambiará su opcode en bloque.

### Selección común de entrega del runner evaluado

La selección no depende de que la familia sea 400. El código original
`aTR` registra sólo si `(Ty || bbW) && (aZN || bbW)`, en su Qf propietario.
`aVo` con eIK falso registra un runner ya evaluado cuando Ty es verdadero,
sin exigir aZN. Los probes originales acreditan esta diferencia con 400,
330 y 649; un ejemplo 193 con Ty falso no se registra por ninguna ruta.

La retención común normaliza ahora únicamente mensajes de UIDs realmente
registrados por el motor, con la misma definición PK que la invocación.
Deriva las máscaras de evento, el retardo `eo(fRR)`, el contenedor y las
banderas de propietario del cliente instalado. Conserva 13497 cuando su
consumidor registra en el manager correcto; utiliza 12613/eIK=false cuando
se acredita Ty y el propietario de la aplicación completa coincide. No
fuerza la retención de mensajes sin UID registrado. La conversión conserva
los bytes de UID/baseUID, PL y TimeDatas.

`native-runner-registration-owners.json` exporta únicamente retornos
booleanos literales comprobados mediante bytecode; los grupos con banderas
dinámicas usan la autoridad existente de sus parámetros. Un propietario
no acreditado sigue rechazado, sin asumirlo por el nombre de la familia.
La lectura de checkpoints reconstruye el antiguo tipo 3 de un hijo de
estado sólo desde su state_uid y el ledger/snapshot fyW efectivamente
conservado; mantiene las áreas 3 y no escribe la base de datos.

Validación: 19 pruebas finales pasan, incluyendo Ready y Sacudida reales
en el motor común, objetivo NPC 4085 nivel 23 con características nativas,
Concentración/Sacudido en ledger, PL 1, entrega 400 por 12613, entrega 330
por 13497 y ausencia de mutación del combate original. Este fixture declara
geometría plana y callback LOS de prueba; no acredita apariencia en GUI.

## Comprobación visual posterior (2026-10-05)

La prueba del usuario tras el despliegue confirmó Concentración visible
con niveles 25 y 35, y Sacudido visible en nivel 30. Esta evidencia acredita
la presentación de estos estados, no la totalidad del hechizo ni de su ciclo.
Permanece pendiente el contador del HUD: `observedCharacter.breedCharacValue`
se obtiene mediante `bkR → bgV.h → bgV.e → eGj.e(ffw).aYS()`, separado
del mapa de estados que utiliza `bgV.j` para el popup. Para Yopuka el valor
es la característica 67 (IOP_RESOURCE), mientras el popup usa el estado
3442. Una instantánea que contiene el estado no actualiza automáticamente
la característica que alimenta el contador.

## Contador de recursos por raza

El productor del HUD se separa de la presentación de los estados. El helper
`combat_hud_resource` proyecta reglas explícitas del servidor emulado:
Yopuka, característica 67 desde Concentración 3442; Sacrógrito, característica
50 desde Furor 9312. No copia automáticamente el mapa de estados del popup.
En particular, 9313 representa porcentaje de vida actual y no Furor.
La proyección conserva los recursos de otras razas hasta acreditar sus reglas.

La raza procede del snapshot de creación del jugador y se conserva en el
checkpoint. El cálculo lee el primer portador nativo ordenado, no suma
portadores duplicados, y se realiza al terminar la resolución y al construir
la instantánea de características. No modifica PW ni ejecuta efectos de
Concentración: los efectos originales siguen consumiendo el estado y
otorgando PW. El contador refleja el nivel resultante después de ese ciclo.

La prueba transaccional del umbral utiliza Ira legal para gastar un PW y
un NPC 4085 nivel 23 con 530 HP nativos. Tras aplicar 100 niveles mediante
el handler original de estado, la rama 193 recupera ese PW y 321 consume
100 niveles; la concentración anterior queda reflejada en la característica
67. Se corrigió la retención de hijos instantáneos: PL/state_uid conserva
identidad pero no fuerza Ty. Antes, reducir el estado deshacía el PW recién
ganado. Quince pruebas del contador, entrada común y retirada de hijos
pasaron. La sincronización del contador en GUI queda pendiente del próximo
despliegue coordinado.

## Revalidación del 5 de octubre: contador e iconos tras reconexión

El usuario confirmó el contador funcionando después del despliegue. Después
reportó ausencia de iconos en Yopuka; al salir y volver a entrar confirmó que
los estados volvieron a mostrarse. Esto acredita recuperación tras reconexión,
pero no determina la causa de la ausencia transitoria.

Los paquetes contemporáneos del lanzamiento de Sacudida de las 04:55:19 UTC
contienen 8913 nivel 30 y su hijo 330/408737 con PL tipo 1, y 3442 nivel 25
con su hijo 400/150327 con PL tipo 1. El probe original de cola y modelo UI
pasó con los payloads sin cambiar el nivel ni el contenedor: 330 por 13497
registra una entrada y una entrada de presentación; 400 por 12613 false
registra ambas. El control 400 por 13497 sigue descartándolas, como antes.
Se añadió `--recorded-pl` a `ProbeNativeStateChildDelivery` para conservar
exactamente el PL registrado. No se modificó el motor para esta revalidación.

La prueba conjunta de 12873 con un bjo aislado todavía no acredita el ciclo
completo: el deserializador llama a registro gráfico global desde
`big.a(int,int,short)` y falla al inicializar dba fuera del cliente. No se
omiten esos callbacks para declarar éxito. Queda pendiente contrastar el
refresco completo en un contexto gráfico aislado; no se manipuló la GUI
del usuario ni se reinició el servidor. El getter obtenido fuera de combate
no constituye evidencia de ausencia de estados durante el lanzamiento.
