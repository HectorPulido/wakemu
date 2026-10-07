# Wakfu/Stasis: valor personal y política ecológica

## Codec y escala comprobados

**13574/cte** transporta i64 ID personaje + i32 **valor absoluto** (12bytes). `cgN.j` resuelve el actor y llama `bjo.Dp(value)` directamente o mediante animación cgQ; `biB.Dp` invalida wakfuGauge/stasisGauge y su tooltip. El parser nativo aceptó personaje12345/valor500. No es delta ni porcentaje.

`fzY.setValue` limita el valor entre−10000/+10000 y convierte a fracción mediante `sign(v)×(1−exp(−abs(v)/(500/log(2))))`. Ejecución: ±500→±0,5; ±10000→±0,99999905; ±20000 se limita a±10000. No usar límites±100 ni una división fija por100. [Probe](probe-jauge-personal-nativa.json). Falta acreditar qué signo muestra cada etiqueta.

## Regla autorizada por el usuario

La política solicitada mide **equilibrio de población**, no simplemente crear/destruir. Plantar con sobrepoblación→Stasis; plantar en equilibrio o escasez→Wakfu; matar población en peligro→Stasis. Mantener/restablecer equilibrio→Wakfu. Esta política configurable del emulador manda aunque otras versiones describan otra regla. La búsqueda específica del sitio oficial no encontró una fuente aplicable; no se adopta fórmula externa ni se afirma que estas reglas sean oficiales.

## Integración concreta del servidor

Persistir entero personal y versión/revisión. Mantener parámetros DB por tipo de acción y estado ecológico; el tamaño de delta y signo se traducen solo después de cotejar etiquetas nativas. Calcular población real por mapa/instancia/región/familia con la autoridad ecológica (issues20/28), no contar clientes ni copiar los ceros del bootstrap actual.

Congelar en recibo conteo antes/después, límites mínimo/máximo vigentes, acción, actor y delta. Para plantación clasificar **antes** de crear, conforme a la regla del usuario de plantar en equilibrio; no invertir resultado porque esa unidad atraviese el máximo. Validar límites ordenados y rango. Para matar usar resultado de combate confirmado y cantidad de monstruos retirada, con atribución verificada a participantes; no conceder en duelo ni por respawn administrativo.

Actualizar recurso/población/valor personal y recibo sin duplicación, confirmar durabilidad y emitir13574 absoluto a las sesiones que deban conocer ese actor. Reintentos pueden reenviar el mismo absoluto sin sumar dos veces. Cancelación/fallo que no cambia población no genera progreso; cosechar semillas sin destruir debe distinguirse de retirar planta.

## Pendientes reales

Rama de signo y bootstrap personal; tamaños de delta configurables con defaults aún por concretar; atribución multijugador; recolección y combate unidos a recibos; reconexión. Ninguno quedó implementado ni reproducido visualmente. Probar escasez/equilibrio/exceso, frontera exacta, dos acciones concurrentes, reintento y saturación.

## Signo y carga inicial resueltos

`bkO` vincula campos wakfuGauge/stasisGauge a `biB.dpW`: positivo alimenta Wakfu, negativo alimenta Stasis por valor absoluto. El tooltip positivo escribe **WAKFU** y el negativo **STASIS**. Queda acreditada la traducción: delta positivo para acciones de equilibrio autorizadas; negativo para sobreplantación o destrucción en escasez.

El bootstrap carga **XP_CHARACTERISTICS**: `sJ` lo identifica como CharacterSerializedXpCharacteristics, `sI.aG` lee i32 en Zz y `bjR.zm` llama `bjo.Dp(Zz)`. Fixture−500 consume exactamente4bytes y restaura−500. En formatos10/11 de entidad exportados existe la sección de4bytes; no asumir que todos los formatos la contienen.

`wire.minimal_entity` incluye XP_CHARACTERISTICS en EMPTY_SECTIONS y escribe ENTITY_DEFAULTS, por lo que no utiliza un valor personal persistido. Integrar aquí un i32 validado−10000/+10000 obtenido de la autoridad del personaje, antes de la rama genérica de vaciado, preservando guarda de hash y layouts. En actualización emitir13574 con el mismo entero absoluto. Repetir bootstrap, actualización, reconexión y observadores sin doble aplicación. No almacenar porcentaje renderizado como si fuera el entero serializado.

La etiqueta y el bloque inicial ya tienen evidencia nativa; aún no se reprodujo una actualización visual ni reconexión de un valor no cero en el servidor. [Probe actualizado](probe-jauge-personal-nativa.json).


## Conteo regional en implementación

El catálogo local acredita `parameter_bKQ` como mínimo y `parameter_bKR` como máximo para familias vegetales; las108 entradas de familias de monstruos contienen0/0, por lo que no aportan límites útiles por familia. Las capacidades regionales no sustituyen esos límites. El snapshot nuevo `ecology_population.snapshot` cuenta filas vegetales activas y miembros de grupos no derrotados por mapa/instancia/región/familia, usando la superficie nativa exactaXYZ. Excluye semillas de monstruo aún no nacidas y etapas0/16. Las posiciones sin superficie acreditada se enumeran como `unresolved` y hacen `complete=false`: no pueden usarse para conceder progreso ni afirmar equilibrio.

Este módulo está **solo en fuente**, pendiente de pruebas e integración transaccional; todavía no modifica la barra personal ni el bootstrap ecológico. Debe ejecutarse dentro de la transacción y bloqueo de población de la acción, antes de clasificar el resultado. Las pruebas aisladas se están preparando; no hay cambios en combate ni hechizos.


## Valor personal y recibos en fuente

Migración026 añade `characters.ecology_value` (entero−10000..10000), revisión y recibos propios por personaje/operación. `personal_ecology.apply` bloquea el personaje, congela delta/evidencia y actualiza valor/recibo en la transacción de su caller. Una operación repetida no suma; evidencia distinta se rechaza. Un recibo antiguo reenvía el valor actual, evitando devolver visualmente la barra a un estado anterior. El encoder13574 publica i64 personaje+i32 absoluto.

Aún no se aplicó026 al servidor ni se conectó el módulo a plantación/cosecha/bootstrap: el personaje sigue sin recibir progreso automático. El caller debe validar lease, población completa y política antes de invocarlo en la misma transacción. Se están probando saturación, concurrencia y rollback en PostgreSQL aislado. El snapshot de población ya pasó3 pruebas aisladas por región/instancia, exclusiones y posición desconocida.


## Política parametrizada en fuente (027)

`ecology_family_limits` separa mapa, región, familia y tipo, con mínimo/máximo, origen y revisión. Migración027 carga159 límites vegetales nativos con máximo positivo. Las filas0/0 y los límites de monstruos no se presentan como umbrales útiles: reciben una política local explícita en `settings.personal_ecology_policy`. Defaults locales: plantas0..100, monstruos1..128; magnitud+25/−25, versión1. Todos se pueden editar en PostgreSQL. No son fórmulas oficiales.

`ecology_policy.decision` clasifica plantar por población **antes** de la acción: hasta el máximo incluido da+25; sobre él da−25. Retirar población se evalúa con el resultado: si queda por debajo del mínimo da−25; en otro caso+25. Cantidad, límites, fuente, revisión y política completa se congelan como evidencia del recibo. Extraer semillas sin retirar población no debe llamar esta ruta.

El gate de migración026, estado personal y conteo pasó14 pruebas PostgreSQL aisladas, incluidos rollback y actualizaciones concurrentes.027 y la decisión se están probando; todavía no se conectaron a acciones ni bootstrap y no se desplegaron.


## Integración vegetal en fuente, pendiente de gate y despliegue

La política, estado personal, conteo y migraciones pasaron21 pruebas PostgreSQL aisladas. Se conectó después `flora_ecology.change` a `planting.complete` exclusivamente en éxito, antes de insertar la planta, y a `resource_collect.complete` exclusivamente cuando la acción retira el recurso (etapa0). El bloqueo advisory `flora-population:map:instance` serializa ambos conteos antes de mutar, sin invertir los locks de grupos de monstruos. Plantas y árboles comparten la ruta; semillas de monstruos aún no vivas y extracción que no cambia población no conceden progreso por esta ruta.

Valor, recibo ecológico, recurso, semilla/producto y XP participan en la transacción de la acción. Fallo/cancelación no llama el progreso. La finalización publica13574 absoluto después del commit; `wire.minimal_entity` carga `XP_CHARACTERISTICS` desde `ecology_value` al reentrar. Una superficie no acreditada conserva la acción de juego pero indica la razón de no conceder progreso, sin adivinar región o población. Los recibos de cosecha conservan metadata ecológica serializable, separada de los paquetes binarios.

Esta integración permanece **solo en fuente**, en gate de regresión antes de recargar el servidor. No se ha verificado aún actualización visual de barra, observadores, atribución de muerte en combate ni siembra de monstruos→nacimiento; el issue7 sigue **En revision**. No se modificaron hechizos ni ejecución de combate.


## Publicación propia y observadores en fuente

Los handlers de finalización vegetal publican13574 después del commit. Actualizan primero el snapshot del personaje en `WORLD` y envían el absoluto a observadores de su mapa/instancia; la conexión propia conserva envío directo, cuyo fallo sigue la limpieza normal de socket. `world_state_packets` añade el absoluto a los snapshots de entrada propia y de nuevos observadores, junto con la montura. Reentrada carga el valor durable tanto en la sección personal como en el snapshot de mundo. No se usa un porcentaje ni se reaplica un delta al reconectar.

No hay ACK de cliente acreditado para13574; no se afirma entrega atómica a todos los sockets. El valor durable permite recuperar al reentrar, mientras que los errores de observadores siguen la desconexión de `World._send`. Esta publicación está en regresión junto con `World` y monturas antes del despliegue.


## Primer gate de integración

Las10 pruebas nuevas de `test_flora_ecology_integration` pasaron: límites preacción, fracaso, superficie desconocida, retirada bajo mínimo, extracción sin retirada, cancelación, rollback de toda la acción, concurrencia y snapshots de mundo. El lote combinado163 tuvo6 fallos en expectativas exactas antiguas de `test_resource_harvest_completion`, por metadata ecológica y13574 nuevos. Se están actualizando esas expectativas con assertions explícitas, conservando cantidades y XP; no se declara el lote aprobado ni se desplegará antes de repetirlo.


## Gate combinado e imagen preparada

Las163 pruebas del lote combinado pasaron después de actualizar las expectativas antiguas con aserciones explícitas de metadata, población, límites, delta y13574; se conservaron las comprobaciones de producto/XP. Se añadió una comprobación pendiente con dos cuentas distintas porque el caso concurrente del mismo personaje ya queda serializado por el lease y no basta para acreditar el bloqueo de población compartida.

Imagen preparada `5459e36d1f3af65a3a34c0f644a2d0e6b78362578f082a96cbd49ae04df1b360`, con026/027. **No recargada ni migrada en la DB real todavía.** El servidor activo continúa en025 mientras el perfil visual completa el ciclo de flora.
