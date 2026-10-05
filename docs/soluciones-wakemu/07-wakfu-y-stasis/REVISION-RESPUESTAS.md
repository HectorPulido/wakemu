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
