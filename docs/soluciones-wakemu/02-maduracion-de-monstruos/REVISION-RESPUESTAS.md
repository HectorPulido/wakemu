# Ecología: revisión de reglas y rutas existentes

## Catálogo comprobado

La familia 68 contiene Jalatín negro (ref 2) y blanco (39), ambos nivel mínimo 4; Jalató (1), mínimo 8; Jalalínea (41), 10; Jefe de guerra jalató (3), 14; Jalató dominante (4085), 18; Jalató Real (44) y Jalabujero el Abandonado (4086), 23. [Extracción de catálogo](../02-maduracion-de-monstruos/familia-68-verificada.json). Ninguna entrada de monsters.json trae `is_boss`. Falta determinar su clasificación nativa; no asumir que todos los máximos de nivel son jefes ni que blanco debe crecer a negro por orden de referencia.

## Qué hace y qué no hace el código

`monster_growth_member` elige una referencia inicial por nivel mínimo y referencia, prefiriendo miembros cuyas acciones dan la semilla. Eso determina el nacimiento desde una plantación; no mantiene un reloj para madurar el NPC adulto ni reproduce sus miembros. La maduración de una semilla y la transformación posterior son mecanismos distintos.

Existe `respawn_monsters` que devuelve grupos derrotados al mundo mediante `respawn_due` y 12608. Solo se lanza con COMBAT_TEST y un intervalo configurado mayor que cero; el default del código es cero. No afirmar que está necesariamente activo en una instancia no inspeccionada. Es una ruta incompatible con el requisito de no respawn artificial y debe quedar deshabilitada/eliminada de la política de población, preservando la liberación de grupos no derrotados.

## Reglas ya respondidas por el usuario

Usar familia y escalones de nivel; ignorar sexo. Evaluar crecimiento probabilístico, más difícil en escalones superiores, en tiempos constantes configurables. Limitar grupos a 8 y evaluar nacimiento y crecimiento por separado. La población nueva procede de semillas, reproducción o el bootstrap inicial único, nunca de regenerar muertos por espera. Pausar actividad de zonas sin jugadores. No quedan decisiones de sexo, familia, máximo de miembros o respawn por preguntar.

## Comprobación restante

Todavía falta reproducir un ciclo de vida completo y determinar clasificación de jefes, codec de sustitución y representación del tiempo pausado. Son investigación técnica. Toda propuesta de fórmula debe marcarse como configurable del emulador, conservar saturación/celdas legales y ensayarse con RNG y reloj controlados. No se ha implementado esta política.


## Registro actual de tareas cotejado por AST

El registro de callbacks en `main` contiene `positions_flush` y, condicionalmente, `builds_flush`/`groups_flush`; **no registra `population`**. La configuración cron declara `population` deshabilitado. Habilitar solo ese switch no implementa evolución ni reproducción: la tarea no tiene callback en esta ruta. `monster_growth_member` selecciona referencia/nivel mínimo al germinar una semilla; no es un ciclo de envejecimiento de criaturas vivas. `respawn_monsters` restaura grupos derrotados mediante `respawn_due`, no acredita reproducción.

La solución necesita servicio de población explícito, reglas/etapas acreditadas, identidad y tiempos durables, y registro del callback junto con planificación/presencia por zona. No reutilizar `groups_flush` como simulación ni representar reproducción como respawn. [Extracción actual](probe-registro-tareas-poblacion.json). No se alteró configuración ni se ejecutó una tarea real de población.
