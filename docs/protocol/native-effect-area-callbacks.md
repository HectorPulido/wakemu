# Áreas de combate: contrato nativo y política del servidor local

El registro Qq/Qs es independiente de los luchadores. El contenedor del área
usa tipo3 y el UID propio; no es el contenedor fyW de un estado ni un actor
fabricado. La geometría se obtiene del prototipo instalado. Se exportaron3624
definiciones alcanzables desde las áreas, verificando colisiones de referencias
al combinar los catálogos.

`Qs` produce10001 al entrar,10008 al moverse dentro y10002 al salir, en ese orden.
Al retirar el área produce10011; la limpieza faV.g utiliza el contenedor exacto
y el administrador correspondiente. HOUR restringe activaciones al propietario;
cero deshabilita activación. Las cargas positivas se consumen en GLYPH;
HOUR conserva sus cargas, porque faZ.bcv() devuelve true.

El alta Qs.a→Qq.bcH no produce10000. La descripción española instalada
`content.67.234` explica que los glifos se activan al iniciar turno dentro.
`NativeAreaEventRuntime.turn_start` propone10000 como política explícita del
servidor emulado, inferida de esa descripción y las máscaras de los prototipos.
No se presenta como código recuperado del servidor oficial. Crear un glifo no
aplica anticipadamente su daño. La entrega2251 sólo se permite desde una
fuente Qe nativa acreditada; una llamada externa sin fuente permanece rechazada.

La conexión permanece detrás de `WAKFU_NATIVE_AREA_CALLBACKS=1`, desactivada por
defecto. Esfera5345 ha pasado creación transaccional de13áreas y su invocación.
Las pruebas unitarias cubren alta sin activación, propietario/cargas/reentrancia
y limpieza por UID/administrador. Falta probar callbacks completos con movimiento
y turnos en la entrada real antes habilitar esta política en el mundo.

## GetActiveSpellId

Token97→eJn→eII.o obtiene la lucha fbX desde el contexto, o desde el personaje
cuando el contexto no ofrece lucha. Devuelve−1 si la lucha o `PZ bah()` es nula;
en otro caso devuelve `PZ.ayn()` convertido a long. No es la referencia del
contenedor del efecto, ni la referencia del efecto disparador.

El servidor local representa ese ámbito mediante `native_active_spell_id`:
fresco=nulo; durante la transacción de un hechizo validado=su referencia; el
ámbito anterior se restaura también en fallos. Esta implementación de productor
es una política del servidor emulado. El probe Java original verifica nulo y
referencia6967; las pruebas Python comprueban anidación, fallo y autoridad ausente.

## Qf propio del área y referencias que sobreviven a Qs

`bcN.a(aKa)` usa `ckD` como propiedades de pelea y `ckE` como propiedades
`fbo` del área. El campo histórico `characteristics` del exportador era un
nombre incorrecto para `ckE`; se conserva como alias y se añaden los nombres
acreditados. La propiedad12 es `GENERATE_RUNNING_EFFECT_MANAGER`: `faV.bax`
crea `eZV` sólo cuando está presente. El probe original confirma1474 sinQf,
1477 conQf y1558 sinQf, todos con radio físico0.

Los estados de1477 viven en un `StateLedger` propio deQq. Aplicar304, registrar
su iterador, retener hijos y resolver su contenedor consultan gestores de estado
sin introducir el área en el roster. No se inventan HP,PA,PM ni turno para ella.
Los estados indefinidos/cero no requieren temporizador de turno; duración positiva
con reloj de área sigue desconocida y se rechaza.

La retirada deQs no elimina referenciasQe/PL todavía acreditadas. El gestor
retirado se mantiene aparte mientras posea estados o referencias retenidas,
queda fuera de consultas espaciales y se libera cuando desaparecen sus usuarios.
La limpieza de callbacks filtra el contenedor exacto (tipo,UID,clase lógicaQq)
para no retirar estados reactivos de otro contenedor.

Prueba de entrada común6967 con innatas y evento inicial de combate: niveles1/200,
coste5PA, creación de2áreas y ningún daño inmediato; inicio de turno del enemigo
dentro del glifo causa5/145HP, respectivamente. El combate original permanece
intacto. Esto acredita la transacción y la política offline; no es validaciónGUI.

### Frontera transaccional de sesión

`combat_area_transaction.prepare_area_event(character, monsters, fight, deck_blob,
actor_id=..., action_id=..., event='turn_start'|'movement', rng=...,
from_cell=..., to_cell=...)` devuelve `(preview, packets)`. La sesión reemplaza
su Fight y emite los paquetes únicamente después de retornar; los fallos
conservan Fight y restauran el RNG externo. Requiere
`WAKFU_NATIVE_AREA_CALLBACKS=1` (predeterminado desactivado).

El comienzo de turno exige el actor `fight.current` de un combate activo.
Movimiento exige que el Fight recibido ya contenga las coordenadas finales
nativas; la sesión debe realizar movimiento y callback sobre una misma copia
antes de publicar ambos. El proveedor se reconstruye con contenedor neutro,
sin suplantar un hechizo activo. La retirada usa el manejador315 existente,
que limpia los hijos con PL del UID exacto del área; no necesita un segundo
callback artificial desde main.

Prueba Feca6967: transición FSM real jugador→enemigo, niveles1/200, área1474
activa5/145HP de daño y cinco paquetes, manteniendo originales intactos.
Esta comprobación acredita el mecanismo offline, no integración mundo ni GUI.

### Integración mundo (fuente, aún sin activar en GUI)

Ready configura `RuntimeMessages.turn_start_provider`; el único punto de entrega
es `turn_started`, después de la expiración inicial del turno. Guarda la clave
`(turn_id, actor_id)` y ACK13510 solamente entrega paquetes pendientes: no vuelve
a ejecutar el callback. `end_turn`, `end_server_turn` y `turn_started` realizan
la frontera sobre copia privada cuando el proveedor está instalado. Un fallo
no publica cambio de turno, HP, reloj, ACK ni paquetes.

`apply_client` y `apply_ai` aceptan `area_provider`; validan/mueven sobre copia
privada y llaman `prepare_area_movement`, que procesa cada casilla en orden
entrada10001/interior10008/salida10002. Sólo después adoptan Fight y runtime.
Una muerte antes del último paso rechaza la transacción completa: aún falta
acreditar la animación/coste truncados. Muerte en la última casilla o por turno
puede acabar el combate y main usa su cleanup existente.

Se corrigió también la depuración de registros tras expiración: el conjunto
vivo incluye los315 propios y StateLedger de Qq con propiedad12. Filtrar sólo
estadísticas/estados de luchadores eliminaba registros válidos del área1474 al
finalizar el turno en nivel200 y hacía fallar la reconstrucción del proveedor.

Verificaciones:46 invocaciones de pruebas de integración/regresión PASS,
además17 invocaciones ligeras de frontera/path PASS (incluyen fixtures importados).
Feca6967 utiliza el RuntimeMessages real y FSM jugador→enemigo en1/200;
confirma5/145HP y que ACK no repite el daño. Pruebas de rechazo comprueban
rollback de turno, movimiento, MP, HP y reloj; la prueba de path comprueba que
el proveedor observa las posiciones intermedias nativas, sin mutar origen.
`WAKFU_NATIVE_AREA_CALLBACKS` sigue predeterminado0. No reinicio ni prueba GUI.


## Checkpoint nativo2251 y retirada843

El productor352198 (familia400, estado7814) acredita2251 desde el canal local1
hacia el Qq real. Qq utiliza el lanzador Qe.bbb() como objetivo de activación;
no transforma el área en un luchador. Se conservan UID, referencia, contenedor,
máscaras y contexto de la fuente. Un Qq con suscripciones propias todavía exige
una autoridad de clonación acreditada y se rechaza explícitamente.

843/eXU→eYc selecciona el Qq explícito, comprueba Qq.bcF (Qr.bdi), emite su
aplicación antes de Qs.b y limpia los hijos con el contenedor exacto. Un Qq
explícito con referencia distinta no cae a selección por coordenadas. La ruta
por coordenada funciona cuando existe un único candidato; varios candidatos
se rechazan porque el orden nativo Trove de Qs.bdm() aún no está acreditado.
Reemplazo eYQ y ejecución retenida de eXU siguen siendo ramas no implementadas.

La activación con objetivo nulo no inventa coordenadas: HOUR la rechaza;
GLYPH puede consumir carga pero faY.c(null) no proporciona celda para hijos.
La retirada HOUR limpia el propietario; GLYPH puede limpiar todos los
administradores reales registrados. Se respeta NOT_ACTIVATED_BY_ALLIES.

Comparaciones con clases originales: ProbeNativeArea843 (6 casos y payload
binario idéntico) y ProbeNativeAreaActivationCharges pasan. 53 invocaciones
integración/regresión pasan, más11 unitarias después de cerrar la selección
ambigua. La prueba duradera Esfera5345 ejecuta el productor352198, desplaza al
propietario y retira el área exacta mediante317642; reconstruye el proveedor y
conserva intacto el Fight original. Flag de mundo sigue0; no acredita GUI.


## Activación del checkpoint soportado

La bandera puede activarse para pruebas Esfera5345/Feca6967 con esta fuente:
Ready instala turn_start_provider; ACK13510 no vuelve a ejecutar la frontera;
movimiento jugador12161 y AI comparten prepare_area_movement. Las transacciones
conservan Fight, recursos, reloj y paquetes anteriores si un callback rechaza.
Se añadieron cierres del combate tras callbacks letales en Ready, ACK y fin de
turno AI; no se inicia otra acción AI después del resultado final.

Las definiciones con máscaras de callback fuera del conjunto acreditado
10000/10001/10002/10006/10008/10011 y fuente2251 se rechazan al registrar el área;
no se ignoran silenciosamente.2251 aún requiere su Qe auténtico. Reemplazo,
retención843, Qq con suscripciones y coordenadas ambiguas conservan rechazos
específicos. No se declara soporte de todas las áreas por activar la bandera.

Checkpoint:25 pruebas en19.582s incluyen Esfera y entradas Feca conflag1;
26 ligeras posteriores incluyen callback letal sin reloj nuevo, ausencia de
segunda entrega, rechazo de máscara desconocida y retirada ambigua. Main
compila. Esta verificación permite la próxima prueba GUI coordinada; no se
reinició ni se cambió la bandera del proceso ya ejecutándose.
