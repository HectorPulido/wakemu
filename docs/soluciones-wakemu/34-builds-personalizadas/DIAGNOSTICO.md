# Diagnóstico — 34

## Contexto registrado

**Reproducido con personaje nuevo en servidor aislado:** Audit Builds, ID 1, subió de 49 a 50 mediante la consola autorizada. El panel de personaje muestra nivel 50 y 550 PdV, pero el panel de builds conserva candado y aviso de disponibilidad desde nivel 50, incluso al cerrar/reabrirlo. El comando actual envía solo `13046` y pide expresamente volver a seleccionar el personaje para actualizar hechizos/puntos. Esta prueba acredita la ruta `!nivel`; la subida por XP necesita su caso propio.

**Repetición solicitada a nivel 100:** antes de reconectar, la ficha mostró 100/1.050 PdV pero el HUD y las builds conservaron el estado anterior. Tras relanzar solo el cliente aislado, desapareció el candado y apareció Build 2. Al seleccionarla se resaltó la fila pero quedó el contenido de Build por defecto; Equipables terminó vacío. El log nativo registra `NullPointerException` al desreferenciar `this.jFr` (modelo de equipo ausente), con `BuildSheetModel` índice 1. Confirma gráficamente el efecto de anunciar una build sin su colección de equipo. No se registró activación 13776 en esta secuencia; no afirmar que se activó ni se probó su deck en combate. El desbloqueo efectivo entre 50 y 100 requiere acotación adicional.

**Contrafactual y activación reproducidos posteriormente:** guardando hojas completas vacías mediante `Store.save_build` solo en Audit Builds ID 1 y reconectando, la secundaria Audit Complete pudo seleccionarse y mostrar Equipables con slots normales. Activarla sí emitió **13776 (9 bytes)** a las 18:09:57 UTC; el servidor autenticado/cargado la rechazó explícitamente por falta de handler. Aunque el cliente mostró Activa, al volver a seleccionar el mismo personaje quedó **Build por defecto Activa**, conservando la hoja secundaria. Esto acredita dos fallos diferentes: bootstrap incompleto y activación sin autoridad/persistencia. No se modificó código ni se probó un cast secundario exitoso.

**Confirmado por protocolo y código:** guardar (`12772`/respuesta `12284`) no activa una build. La selección nativa emite **13776**, con ID e índice, y el dispatcher no tiene handler. `Store.character` no carga una selección persistida; equipo y aptitudes usan índice 0 por defecto. El bootstrap `build_set` anuncia activo 0 aun cuando el diccionario de entrada tenga índice 2. Tanto listo como lanzamiento de hechizos leen explícitamente el deck 0. Es necesario corregir la transición completa, no únicamente el desbloqueo visual.

**Confirmado con pruebas aisladas:** en niveles 1/49/50/51/200, las colecciones nuevas anuncian builds `[0,1]`, aptitudes `[0,1]`, equipo `[0]` y decks `[0]`. Tras guardar builds secundarias con contenido, los registros sí las incluyen; la inconsistencia no afecta por igual a todos los casos. En nivel 51, una build secundaria con amuleto y aptitud propios produce **588 PdV y +1 PA** al evaluarla explícitamente, mientras el cálculo normal conserva **560 PdV y ningún equipo**. SQLite y el journal guardan las hojas, pero recargar pierde cualquier selección añadida solo al diccionario. También se reprodujo `Invalid aptitude sheet level` al subir de 49 a 50 con una hoja guardada con nivel fijo 49.

**Posible solución exclusivamente del servidor:** fuente única de builds disponibles/activas y hojas coherentes de equipo, aptitudes y decks; desbloqueo sincronizado tras progresión; activación autoritativa de 13776 con selección persistida/versionada; estadísticas y combate resueltos desde ese índice; recuperación y rechazos sin bloqueo ni pérdida de hojas. Distinguir hoja a nivel real (`-1`) de nivel limitado antes de ajustar validaciones. No reutilizar `12837`, que corresponde a borrado de build, como ACK de activación.

**Comprobación ampliada:** 40 tests enfocados ejecutados OK (10 omitidos por requerir Redis), 9 de journal con Redis real OK (1 omitido de inyección de caída) y 44 filas experimentales con assertions de evidencia. No equivalen a probar la interfaz completa ni a solucionar el problema. Detalles, artefactos, límites y resultados gráficos en [auditoría profunda del issue 34](../../reports/auditoria-builds-issue34-wakemu-2026-10-04.md).

## Lectura actual

Metadata anuncia {0,1,*saved} y activo 0; equipment_registry y deck_collection no anuncian automáticamente la secundaria 1 no guardada. Esto confirma colecciones inconsistentes, además de activación ausente.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Respuesta nativa de 13776 y recuperación de heroBuildLock.
- Configuración de desbloqueo y significado del cupo visible de 24.
- Política de modulación y salud al alternar builds.
- Recorrido gráfico de borrado y combate con un hechizo exclusivo de una secundaria.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
