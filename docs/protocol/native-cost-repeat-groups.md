# Grupos nativos 910, 912 y 949

Fuentes: registro eVj instalado, `eYt.C/d`, `eYv.C/d/a`, `eXL.G/H`, `eXN.C/c`, `eZM.l`. Bytecode conservado en `.runtime/local/native-cost-repeat-groups.txt`, `native-repeat-base.txt`, `native-repeat-group-base.txt`. Probe reproducible: `sniffer/java/ProbeCostRepeatGroups.java`.

## 912: coste de la acción que dispara el listener

`eYt` extiende `eYg`: conserva los seis parámetros del grupo normal y añade tres pesos FLOAT (PA, PM, PW) en parámetros 6–8. Solo una fuente concreta `eWf` aporta los bytes `fMH/fMG/fMF`. Suma los tres productos en float32 en ese orden y aplica `Math.round(float)`. Una fuente ausente o de otra clase conserva el override SP=-1. No se usa el valor de daño, ni se consulta el coste del hechizo en esta familia.

El probe usa la definición real 348490: fuente eWf con cuatro PM produce nivel 4; fuente nula/otra conserva -1. También comprueba redondeo negativo.

## 910: coste del hechizo que dispara el listener

`eYv` conserva esos mismos parámetros, pero consulta un contexto diferente. Para una fuente que cumple `oz(500)` utiliza el hechizo/nivel actual de PN. Para otras usa el contenedor de la fuente, que debe tener tipo 11 y ser fyG. Fuente nula, contenedor nulo o de otro tipo produce SP=0.

Con caster eGj usa los costes `fyF.h/g/e` resueltos en el contexto vivo caster/target/PN; para otros caster usa las tablas `aai/aal/aaj` del nivel fuente. Los costes pagados de eWf no sustituyen esa lectura. El helper requiere una instantánea explícita de costes ya resueltos; todavía falta acreditarla automáticamente en todos los productores de eventos. Si ese contexto es desconocido, rechaza la activación.

## 949: repetición de hijos

`eXL` extiende eXN/eZM, no eYg. El primer parámetro fija repeticiones con máximo nativo de 12; valores negativos ejecutan cero iteraciones. El segundo parámetro habilita detenerse cuando vale exactamente 1.

Cada iteración visita hijos en orden y reinicia los contadores PT. Un PT creado con `bas()==0` cuenta como fallo; PT nulo no lo hace. El hijo recibe la celda del padre y objetivo actor nulo: su propio targeting debe seleccionar candidatos. No se reutilizan parámetros ni rebind del grupo330.

`combat_repeat_group.execute_repeated_group` exige resultados explícitos `RepeatChildOutcome(pt_created, applications)`. El booleano del dispatcher actual no acredita la diferencia PT nulo frente PT.bas cero: falta integrar ese puente antes de habilitar el executor completo. El helper rechaza booleanos ambiguos.

El probe verifica la definición real 379582: seis repeticiones y detenerse por fallo. Cuatro pruebas Python cubren costes/fuentes, repetición/límite y la diferencia PT nulo/PT cero. Esto acredita primitivas y registro, no gameplay ni los eventos productores que aún no tienen contexto completo.

## Integración viva de costes

`combat_event_costs.source_cost_descriptor` se conecta a los eventos ordinarios eXs/eXt: transporta el contenedor nativo de la fuente, su hechizo/nivel cuando es tipo11, y no congela costes antes del rebinding del listener. `LiveEventCostAuthority` se conecta al factory y al contexto serializado de hijos. Resuelve tablas/condiciones/modificadores eHl contra caster y target del listener en el preview de la transacción. Un hechizo fuente de otra raza no se rechaza por ownership del listener.

Cinco pruebas adicionales incluyen emisión automática de las ocho fases/canales ordinarios con descriptor6266/1, conservación del descriptor sin costes precalculados, resolución real6260 con modificador vivo que cambia5→2, y el callback del árbol910/308144. Diez pruebas previas de curación/daño ordinario pasan. La condición nativa de308144 contiene `and False`: se conserva; probar su primitiva no acredita activar esa pasiva en juego.

La producción automática de un evento de pago eWf y la rama fuente500/current-PN siguen pendientes de auditoría de su lifecycle. 912 soporta instantáneas pagadas explícitas acreditadas; los eventos eXs/eXt son `other` y conservan el nivel padre, como el cliente.

Para949, `eVE.a(PL,PV,PN,UJ,...,true)` devuelve PT nulo si falla su guardia geométrica privada o no existe runner en UJ. Después `Qe.a` crea PT antes de seleccionar objetivos, por lo que un selector vacío puede producir PT creado con cero aplicaciones. La guardia privada comprueba fKX, amQ, actores/faV y QI.R/V; no equivale a la caminabilidad. Fuente: `.runtime/local/native-effect-pt-creation.txt`. El puente de creación/contador debe acreditar esas guardas antes de ejecutar949.
