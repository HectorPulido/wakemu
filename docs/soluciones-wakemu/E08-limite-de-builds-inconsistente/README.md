# E08. Cupo de builds e índices nativos

El servidor ya separa el índice representable de la cantidad de hojas no permanentes: acepta índices dispersos entre0 y127, cuenta el cupo por cantidad y obtiene `non_permanent_build_limit` desde PostgreSQL. El valor se valida en el rango1–24, persiste al reabrir y gobierna el guardado de builds. El carrier22318 publica `non.permanent.build.limit` con el límite actual antes del bootstrap23082 y junto con respuestas de guardado/rechazo. Índice0 conserva clasificación predeterminada/permanente; metadata enviada no puede convertir otra hoja en permanente ni retirar esa clasificación.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo](COTEJO.md) · [Implementación](IMPLEMENTACION.md) · [Pruebas](PRUEBAS.md) · [Pendientes](FALTANTES.md)

## Estado y límites

**Parcialmente implementado.** El gate PostgreSQL de aptitudes/builds/equipo pasó 54 pruebas. Verifica lectura/reapertura de la política y validación de cupo incluso a través de `Store.save_build`, más el carrier exacto del límite y los bordes de byte e índices dispersos. La decodificación nativa aislada confirma que el delta cambia 24→1 y conserva `calendar.delta7`. Sigue pendiente verificar visualmente que el contador de UI cambia y se mantiene correcto en la sesión real, además de aceptación visual de creación, selección y borrado.

Dependencias: 34, E04 y E07. No se amplió el motor de hechizos.

## Contador visual confirmado

El usuario creó una hoja adicional y observó 1/24; al crear otra observó 2/24, con la predeterminada visible aparte. Es correcto: `bhp.eH("countAndLimit")` obtiene el numerador de `eQW.fHo()`, que cuenta únicamente hojas donde `eQT.dla()` es falso. La hoja permanente predeterminada queda excluida. El denominador procede de `eQZ.fHr()` y `non.permanent.build.limit`. Este resultado valida el conteo inicial, no la prueba del límite completo ni el borrado.
