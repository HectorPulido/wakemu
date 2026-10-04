# Probabilidad relativa de grupos de efectos

Revisión del cliente instalado: `eYg.c(Qe, boolean)` y `UK.pT(int)`.

La rama relativa no elige un único hijo por pesos. Primero construye candidatos y suma probabilidades; después realiza un sorteo independiente por cada candidato. Puede conservar ninguno, uno o varios. Sustituirlo por una elección ponderada cambiaría los hechizos.

Orden observado:

1. Recorre hijos en orden de catálogo. Consulta `amQ.a` con lanzador, contexto, área, celda y selector del hijo. El bytecode salta el hijo cuando ese iterable tiene elementos; es necesario auditar el significado exacto de este resultado antes de reutilizar el resolver normal.
2. Filtra por nivel mínimo/máximo. Los suscriptores (`aZN`) se incorporan sin evaluar el criterio aquí; otros requieren criterio válido cuando existe.
3. Suma `eg(level)` mediante float32, conversión a entero Java y narrowing short **en cada suma**.
4. Para cada candidato, compara `UK.pT(total)` con `UP.bt(probabilidad)`. `pT` devuelve un entero entre 1 y total inclusive; con total no positivo devuelve 1. `UP.bt` exige su redondeo aleatorio nativo.
5. Retira candidatos cuyo sorteo excede el umbral y ejecuta los restantes con contexto `eVt.a(true, false, parent)`, lo cual cambia el tratamiento posterior de probabilidad.

Pendientes antes de conectar: significado de los candidatos de `amQ`, autoridad de criterios y nivel, RNG y su consumo exacto, contexto de hijos y grupos con modo de éxito/límite. No se habilita una aproximación de elección ponderada.

Evidencia local: `.runtime/local/native_relative_group.txt` y `.runtime/local/native_relative_rng.txt`, extraídos mediante javap del JAR instalado. Revestimiento Absoluto continúa pendiente; esta revisión no declara su funcionamiento.

## Componente de cálculo

`combat_relative_probability.py` reproduce la suma short por paso y sorteos independientes con callbacks explícitos. Cuatro pruebas cubren varios/ningún hijo, truncamiento fraccionario por paso, orden de RNG y overflow. `UP.bt` usa floor y Bernoulli de la fracción; `GT.l(0)` no consume RNG. La suma no positiva tampoco consume RNG en `UK.pT`. Este componente aún no está conectado al dispatcher: faltan candidatos y contexto nativos, por lo que la pasiva sigue pendiente.

## Candidatos: origen acreditado

`ProbeNativeRelativeCandidates.java` ejecuta `amQ.a` real con selector nulo y área punto. Con caster y actor en (0,0), cambiar la celda a (10,10) conserva el actor; mover caster a (10,10) lo excluye. `anc.a` y `amX.a` confirman que el origen usado es caster y la celda participa en orientar. El experimento anterior no fallaba por un proxy de posiciones: revelaba una suposición incorrecta de área centrada en celda. Corregida la interpretación; no extrapolar a selectores fcE sin auditar su rama. El resultado no vacío confirma la exclusión que hace la rama relativa de eYg. Se notificó este hallazgo al responsable del resolver común.

El filtro común `relative_eligible_candidates` está implementado y probado: respeta la exclusión del iterable no vacío, límites de nivel y bypass de criterio para suscripciones. La población desconocida se rechaza. Seis pruebas del módulo pasan. Falta producir esos snapshots desde la autoridad de selección y transmitir el contexto de probabilidad relativa a los hijos en el dispatcher.

## Provider común conectado mediante hook

`RelativeGroupAuthority` implementa el contrato `NativeEffectRuntimeFactory.relative_group_children`, usando roster y propiedades de la autoridad ordinary, selector/área nativos, criterios vivos y RNG explícito de la transacción. Lee elegibilidad y `eg` al nivel del padre; no usa el override dinámico de999 para esos filtros. Si hay fuente de evento, el criterio usa su caster como indica eYg; una suscripción omite esa evaluación. El dispatcher ya transmite el contexto eVt de probabilidad relativa a los hijos seleccionados.

El probe ampliado ejecuta `amQ` real con fcE máscara1 y punto: celda ocupada produce iterable no vacío (el padre excluye ese hijo); celda vacía produce iterable vacío. El selector nulo conserva el origen en caster. Cuatro nuevas pruebas del provider y seis del cálculo pasan.

La herramienta `server/tools/audit_relative_initialization.py` instala innatas y Revestimiento Absoluto6936 (árbol344011) a niveles60 y200 con instantáneas completas y autoridad ordinary. Ambos casos inicializan, conservan rollback y tienen hashes estables: `docs/reports/combat-inventory/relative-initialization-audit.json`. En la celda ocupada de inicialización, el hijo344012 se excluye por la regla observada; no se atribuye un bono de HP que no se haya aplicado ni se afirma funcionamiento jugando. Roster muerto, radios no nulos y actores fuera de la autoridad ordinary quedan rechazados hasta acreditar esas variantes de amQ.
