# Grupo 345: selección múltiple eYC

Auditoría del cliente instalado, 5 de octubre de 2026. Selector, rama del
dispatcher, autoridad compartida de candidatos y RNG transaccional conectados.
La notificación propia se suprime mediante fRS sin eliminar su registro retenido.
La entrada común y una cadena de hojas originales están probadas offline;
esto no acredita todavía gameplay en el cliente.

## Parámetros y ejecución

`eYC.C` interpreta, al nivel `fRR`, hasta cuatro parámetros: cantidad máxima
`rGu`; filtro de criterio por candidato `rGv` (solamente valor 1 lo activa);
barajado `rGw` (solamente 1 lo activa); orden `ePP`. Los valores por defecto
de `aWr` son -1, false, true y 0. La lista de hijos procede de fyE/fyD al
mismo nivel. El clon copia cantidad/filtro/barajado; C vuelve a sembrar el orden.

`eYC.c` suprime su propia notificación PR con `fRS`. Obtiene candidatos a
través de `eYE.e(this, rGv)`: éste llama al selector compartido `eZR.a` con
definición, caster, PN y celda actual `bbd` incluyendo altura. No constituye
una iteración universal de todos los actores. Con filtro activo evalúa
`definition.fKT().b(caster, candidate, runningEffect, PN)` por candidato.
Sin criterio definido conserva el candidato. Con filtro activo `eYC.I`
devuelve true y evita aplicar el criterio del grupo una segunda vez sobre
un único objetivo.

Después baraja la lista si rGw, y **después** la ordena si ePP>0. El orden es
estable; empates conservan el orden resultante del barajado. `faf.Te` reconoce:

- 0/NONE: comparador que devuelve siempre cero.
- 1/SPIRAL_SORT: distancia Manhattan al caster, seguida de ángulo
  `atan2(y-casterY, x-casterX)` en grados, normalizado a [0,360).
- 2/INVERTED_SPIRAL_SORT: inversión del comparador compuesto completo.
- Cualquier otro ID: NONE, no rechazo ni orden inventado.

El centro de orden es `caster.baM()`, distinto de la celda de selección.
Altura y radio físico no forman parte del comparador. La cantidad se cambia
por `min(list.size(), rGu)`; una cantidad negativa no ejecuta hijos.

Para cada candidato seleccionado crea un contexto eVt con `(false,false,
triggeringSource)`. Si tiene flag16 y override SP==-1 transmite `fRR`.
Ejecuta la lista completa de hijos mediante `eVn.a`, pasando PL del grupo,
caster, PN, **XYZ y altura del candidato**, PV explícito candidato, contexto
y booleano final false. Cierra el contexto mediante `bal` también al fallar.
No se debe convertir el PV explícito en una selección por área reconstruida.

## Contrato integrado en el motor común

El proveedor de candidatos debe llamar a la autoridad de selección existente
con el contexto actual, no mantener un roster alternativo. El criterio por
candidato usa esa misma invocación/fuente. Barajado consume RNG transaccional;
ordenación estable usa coordenadas autoritativas del caster y candidatos.
El ejecutor común recibe cada hijo con celda y PV del candidato y contexto
nuevo, conservando nivel/PL y la transmisión flag16 acreditada. Las ramas de
suscripción, UID y retirada siguen bajo retención común. Los hijos pasan por execute_pt, conservando el preflight compartido.

## Probe reproducible y límites

`sniffer/java/ProbeNativeGroup345.java`: **25 comprobaciones PASS** con métodos
originales eYE, eYC, faf y sus comparadores. Comprueba criterio opcional,
coordenadas de selección, espiral e inversión, sort sobre PV, ejecución
de todos los hijos con PV/XYZ reales, copia y reset. No carga bdata.

```sh
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/javac -proc:none -cp 'client/lib/*' -d .runtime/local/classes sniffer/java/ProbeNativeGroup345.java
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/java -Xmx128m -cp '.runtime/local/classes:client/lib/*' ProbeNativeGroup345
```

El probe sustituye únicamente la fuente de candidatos por una lista explícita
para aislar el filtro original. No demuestra elegibilidad completa del roster,
barajado reproducible de Java, creación real de PT, retención ni gameplay.
La transmisión de contexto/flag16 y el orden de barajado/mincount se acreditan
por bytecode en `.runtime/local/common-families430-345.txt`. Los comparadores
se conservaron en `native-group-345-selection.txt`, `native-group-345-sorts.txt`,
`native-group-345-spiral.txt` y `native-group-345-point.txt`.

Regresión Python: 20 pruebas PASS de selector, resolver y dispatcher
en 4,923 segundos. Incluye filtro antes del barajado, empate estable, cantidad,
PV directo, altura del candidato y ejecución de todos los hijos. No sustituye
una transacción de un hechizo nativo ni valida el ciclo retenido completo.

## Ejecución con datos instalados

Arcabuz 6475, raza 13, niveles 13 y 200, normal y crítico: cuatro
transacciones completas mediante server_runtime ejecutan daño y consumen 4 PA,
con fuentes estables y rollback del original. Los grupos 370906/370940 se
alcanzan, pero su criterio original excluye los objetivos ya marcados por
las raíces anteriores. Por tanto estos lanzamientos no prueban activación
positiva de los hijos de 345. Los informes group345-common-0/1.json conservan
los resultados y las fuentes.

La herramienta server/tools/probe_native_group345_runtime.py ejecuta por
separado esas hojas originales y sus cadenas 370910/370944 después de Ready
real, con dos NPC 1367 nivel 115 (3000 HP nativos), snapshots y alturas
autoritativas. En cuatro casos selecciona el primer NPC y después el segundo,
aplicando estado 3656 a niveles 2 y 3. Mantiene los criterios originales y
suprime PR propia de 345. El informe group345-native-leaf-runtime.json registra
paquetes, selección, fuentes y rollback. Esta prueba aislada no descuenta
costes ni representa la ejecución completa del hechizo.

Cinco pruebas ligeras específicas cubren selección, PV y altura, todos los
hijos y la separación entre supresión de PR y retención. No se ha verificado
esta familia en GUI ni una activación positiva de 345 dentro del lanzamiento
completo 6475. El RNG Fisher–Yates conserva la distribución original y la
transacción; no reproduce la secuencia binaria del generador Java.
