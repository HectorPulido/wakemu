# E04 — avance de implementación

La transición de persistencia existe como `Store.activate_build`, con lease, catálogo, fase, revisión y salud transaccionales. Ver [evidencia E05](../E05-seleccion-build-y-deck-cero/IMPLEMENTACION.md).

El dispatcher aún no integra13776 ni su respuesta13811; E04 no está resuelto. Antes de habilitarlo, verificar recuperación de selección optimista y sincronización de las colecciones/efectos con el consumidor nativo. No se modificó el motor de hechizos.

## Handler conectado (sin despliegue todavía)

13776 se decodifica como i64 de actor y byte con signo de índice, longitud9 estricta. Actor ajeno, índices negativos, truncado y bytes adicionales rechazan. El dispatcher llama a la transición transaccional y responde13811 con la selección autoritativa; el rechazo devuelve la selección anterior y registra la causa. Activación durante combate no se confirma ni publica snapshot fuera de combate.

Tras éxito se envía snapshot de estadísticas fuera de combate. El lector nativo13811 llama `eQX.R`, que verifica la hoja y selecciona `eQW.QT`; resta contrastar el comportamiento visual y sus efectos locales.

Suite54 casos: **43 PASS y11 SKIP**. Codec, selección autoritativa y transición de Store cubiertos; no equivale a prueba de cliente. Faltan HP con equipo de máximos distintos, Redis real, deck de combate y rollback visual. No modificar motor de hechizos sin coordinación.
