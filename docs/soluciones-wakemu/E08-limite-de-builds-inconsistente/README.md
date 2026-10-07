# E08. Cupo de builds e índices nativos

El servidor ya separa el índice representable de la cantidad de hojas no permanentes: acepta índices dispersos entre0 y127, cuenta el cupo por cantidad y obtiene `non_permanent_build_limit` desde PostgreSQL. El valor se valida en el rango1–24, persiste al reabrir y gobierna el guardado de builds. El carrier22318 publica `non.permanent.build.limit` con el límite actual antes del bootstrap23082 y junto con respuestas de guardado/rechazo. Índice0 conserva clasificación predeterminada/permanente; metadata enviada no puede convertir otra hoja en permanente ni retirar esa clasificación.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo](COTEJO.md) · [Implementación](IMPLEMENTACION.md) · [Pruebas](PRUEBAS.md) · [Pendientes](FALTANTES.md)

## Estado y límites

**Solucionado totalmente.** Gate PostgreSQL de aptitudes/builds/equipo:54 pruebas OK, incluidos índices dispersos, límite de guardado, reapertura y carrier22318. El usuario confirmó el ciclo completo con Npers:24/24 deshabilita crear, borrar la activa vuelve a predeterminada y23/24, reemplazo y reconexión correctos. Cotejo SQL: personaje6/cuenta2,24 hojas personales con índices1–24; índice24 corresponde a CupoReemplazo y selección activa24, revisión3. Política PostgreSQL24. No se observaron hojas adicionales fuera del cupo.

Dependencias: 34, E04 y E07. No se amplió el motor de hechizos.

## Contador visual confirmado

El usuario creó una hoja adicional y observó 1/24; al crear otra observó 2/24, con la predeterminada visible aparte. Es correcto: `bhp.eH("countAndLimit")` obtiene el numerador de `eQW.fHo()`, que cuenta únicamente hojas donde `eQT.dla()` es falso. La hoja permanente predeterminada queda excluida. El denominador procede de `eQZ.fHr()` y `non.permanent.build.limit`. Este resultado valida el conteo inicial, no la prueba del límite completo ni el borrado.

## Aceptación del límite completo — 6 de octubre

La prueba manual del usuario acredita el bloqueo visual en24 y la restauración del cupo al borrar. PostgreSQL confirma el reemplazo y la selección persistidos. La hoja predeterminada permanente no cuenta dentro de esas24. Este cierre corresponde al cupo E08; modulación, salud y decks secundarios del issue34 siguen independientes.
