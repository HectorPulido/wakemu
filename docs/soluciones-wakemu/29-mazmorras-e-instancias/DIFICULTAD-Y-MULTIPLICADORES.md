# Dificultad: tablas nativas de recompensa

## Fuente y prueba ejecutada

Se ejecutó un decodificador privado de `aNv`/`aKX`/`bcA` del contenido instalado. El estado 7447 contiene seis grupos. `ffw` identifica característica 115 como `XP_EARNED_FACTOR` y 116 como `DROP_RATE_FACTOR`. No son vida/daño.

`bam` carga grupos 335583 y 335577, almacena `100 + So(0)` por índice `fKR` (1–10), y `brq.Y` consulta `eQN.g` para calcular el porcentaje mostrado de loot. `brE.gU` actualiza `displayCompetitiveMode`; `false` selecciona 335583 y `true` 335577. `brE.FE` limita el selector a 1–10. Esto acredita la tabla usada por la UI instalada, no la ejecución de RNG/recompensas del servidor.

| Nivel | Drop normal | Drop competitivo | XP normal | XP competitivo |
| --- | --- | --- | --- | --- |
| 1 | 0.6× | 0.6× | 0.6× | 0.6× |
| 2 | 1× | 1× | 1× | 1× |
| 3 | 1.2× | 1.4× | 1.2× | 1.4× |
| 4 | 1.6× | 2.5× | 1.6× | 2.5× |
| 5 | 1.88× | 4× | 1.88× | 4× |
| 6 | 2× | 5.5× | 2× | 5.5× |
| 7 | 2.05× | 6× | 2.05× | 6× |
| 8 | 2.1× | 6.5× | 2.1× | 6.5× |
| 9 | 2.15× | 6.8× | 2.15× | 6.8× |
| 10 | 2.2× | 7.1× | 2.2× | 7.1× |

Se extrajo `aNw.cyi`, el texto que `bcA.j` compila como criterio: grupos 335565 (XP) y 335577 (drop) requieren `GetInstanceLevelMax() > 0`; grupos 335571 (XP) y 335583 (drop), `GetInstanceLevelMax() <= 0`. Esto resuelve la selección de las dos series. El límite de nivel de instancia debe venir de estado autoritativo, no de un checkbox del cliente.

## Orden del cálculo de loot mostrado

`brq.Y(base)` combina el factor de dificultad con otros bonus **de forma aditiva respecto de 1**, después aplica otros factores y limita el resultado a 1 (100%). No es correcto multiplicar indiscriminadamente dificultad × cada bonus. El consumidor usa campos adicionales de personaje y opciones de enciclopedia; todavía hay que acreditar sus nombres y la equivalencia con el cálculo autoritativo del servidor. La precisión visual del tooltip no demuestra redondeo del RNG.

## Lo que sigue pendiente

Identificar efectos exactos de vida/daño/resistencias, condiciones de rareza y elegibilidad, modulación, redondeo y recompensa efectiva por participante. El grupo 335591 incluye metadatos de efecto genérico 1102; sus parámetros no se convierten aquí en una fórmula inventada. No usar documentación de versiones con 50 niveles para sustituir este selector instalado de diez.

[Valores derivados de la prueba](probe-dificultad-recompensas.json). No se distribuyen archivos ni clases del cliente.

## Efecto 1102: función real cotejada

El registro nativo `eVi` vincula **1102 → eYp**, un generador de efectos hijos cuyo nivel depende del nivel mínimo de mazmorra. No representa directamente un porcentaje de vida/daño/resistencia. `eYp.C` resuelve el grupo hijo, evalúa parámetros 1/2 y lee contexto `fBf.rI` (valor por defecto 0 sin contexto); `d` fija el nivel del efecto hijo mediante **`Math.round(rFD + rFE * contexto)`**. Se verificó el método de contexto mediante el bootstrap de la lambda del bytecode.

Esto concreta el siguiente cotejo: grupo hijo, características modificadas por sus efectos y evaluación de parámetros a la dificultad real. No convertir los seis valores crudos del catálogo en multiplicadores porcentuales ni usar truncado de Python en lugar del redondeo nativo. No se ejecutaron hechizos ni efectos; inspección estática únicamente. [Evidencia](probe-runner-escalado-nivel-hijos.json).

## Grupo 335591: hijos de recompensa, no estadísticas

La extracción adicional de grupos resolvió `335592 → 335593` y `335594 → 335595`; ambos hijos son **genérico 987**, parámetros `[24029,0,0,1]`. El registro `eVi` identifica 987/`eWg` como concesión de un objeto bonus al final del combate. Por tanto, esos generadores 1102 pertenecen al escalado de una recompensa del objeto **24029**, **no** a vida/daño/resistencias. Se descarta la hipótesis de interpretar 24029 como estado: el loader de estados no encontró esa referencia y el registro acredita semántica de objeto.

El grupo 335596 contiene hijos 421 con referencias 308227 y 308229, todavía por seguir. Debe cotejarse la cantidad, elegibilidad y nivel efectivo de la recompensa; el escalado de estadísticas se investiga por otra ruta. Esto evita declarar resuelta la fórmula de HP a partir de efectos de loot. [Metadatos ejecutados y límites](probe-hijos-escalado-recompensa.json).

## Segunda rama: retirada de efectos anteriores

El registro nativo acredita **421/eXe** como retirada de efectos (desencantamiento), no modificación directa de características. Los hijos de 335596 apuntan a 308227/308229; el catálogo de metadatos identifica 308229 como efecto 987 del objeto bonus 24029, mientras 308227 no aparece en ese catálogo. La búsqueda de grupos aKX con esos IDs tampoco produjo grupos: no tratarlos como grupos hijos ni como HP. Queda por cotejar la política exacta de retirada y la referencia ausente. Esto confirma que esta rama no aporta la fórmula pendiente de vida/daño.


## Estadísticas de la enciclopedia: funciones ejecutadas

Se rastreó `bro.a(short,ffw,int)` desde la dificultad seleccionada en `brE → brC.dIu`. La rama de PV usa el tipo de mazmorra asociado al monstruo; si hay varios tipos combina sus intervalos. Se ejecutaron las funciones privadas nativas en **150 combinaciones**: 10 dificultades, cinco tipos y tres bases (1, 101, 1000).

| Tipo | Factores de PV, dificultades 1–10 |
| --- | --- |
| Tres jugadores / dos salas | 0,7; 1; 1,6; 2,4; 4; 5,5; 8; 9; 11,5; 14 |
| Jefe supremo | 0,7; 1; 1,6; 2,4; 3,6; 5,2; 7,4; 8; 10; 13 |
| Tres / cuatro salas | 0,7; 1; 1,4; 2,1; 3,1; 4,4; 6; 6,6; 8,8; 11 |

La función devuelve intervalo mediante `GS.B/GS.C`, no un único entero: base 101 a dificultad 1 produce **70–71**. `ffw.shF` es **WILLPOWER (voluntad)**: suma 0 en dificultad 1–2, 10 en 3–4, 20 en 5–7 y 30 en 8–10. PA y PM suman 0 en 1–4, 1 en 5–8, 2 en 9 y 3 en 10. No etiquetar voluntad como daño o resistencia.

Estos valores acreditan el cálculo de presentación del cliente instalado. Para la solución del servidor, conservar tablas por tipo/dificultad como parámetros versionados en DB y cotejar su aplicación al construir actores de combate; no alterar estadísticas base del catálogo ni multiplicar nuevamente un actor ya escalado. La misma configuración debe alimentar entrada, estado de instancia y recompensas, manteniendo separados los factores de PV de XP/drop.

**Límites:** falta cotejar la aplicación efectiva en combate, los modificadores de daño/resistencia y la relación de tipos para cada monstruo. La función no contiene un selector competitivo: no inferir de ello que todas las estadísticas de combate coincidan en ambos modos. Tampoco resuelve la composición de salas. [Probe y resultados derivados](probe-escalado-estadisticas-enciclopedia.json).
