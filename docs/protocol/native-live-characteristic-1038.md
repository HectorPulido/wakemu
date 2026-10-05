# Característica vinculada 1038 — auditoría pendiente de integración

Cliente instalado, 5 de octubre de 2026. El registro eVi vincula 1038 a eWh,
subclase de eWa. Esta familia no equivale a aplicar una bonificación eWQ una
sola vez: instala un listener PD sobre el PA fuente y mantiene una contribución
reversible en el PA destino. Todavía no hay handler registrado para 1038.

## Contrato original

C reinicia Qe.amount a -1 y lee IDs fuente/destino (p0/p1), inversión (p2==1),
ratio porcentual p3 (100 por defecto), límite máximo de modificación p4 (0 por
defecto, sólo se aplica cuando >0) y mínimo p5 (Integer.MIN_VALUE por defecto).
Los IDs se convierten a byte antes de buscar ffw.

En eWa.c, inversión false toma PA fuente del target y PA destino del caster;
true toma fuente del caster y destino del target. Ambos deben ser fff. Crea
un eWi, lo suscribe mediante source.a(PD) y lo ejecuta inmediatamente con ese
PA fuente. Fuente o destino nulos suprimen PR mediante fRS.

En eWi.a(PA):

1. Destino.oo(retainedContribution) retira la contribución anterior.
2. Calcula int32(source.aYS()*ratio)/100 con división entera hacia cero.
3. Limita primero por el máximo positivo, después por el mínimo explícito.
4. Destino.nG(calculated) agrega el valor y devuelve la contribución actual
   clamped; eWi la conserva para la próxima actualización y retirada.

cancel retira exactamente la contribución retenida. bLM elimina el listener
del PA fuente. eWa.bbR llama cancel+bLM solamente si Ty es true; después usa
la retirada común eZR. Esto requiere distinguir identidad del owner/manager,
PA fuente y PA destino, y no recalcular una contribución al retirar.

AdditionalDatas emplea el mensaje ij/il: Mc=inversión, Mg=ratio, LT=ID destino,
getValue=máximo y Mi=mínimo; Qe.amount contiene ID fuente. El codec debe
contrastar números de campo originales antes de emitir un paquete.

## Integración necesaria

Se necesita ledger dinámico por UID y una interfaz de notificación de cambios
PA que mantenga el orden nativo: actualización del recurso → listeners →
criterios posteriores. Un barrido al final del cast no equivale a ese contrato,
pues los hijos y reacciones pueden consultar el destino intermedio. El ledger
ha de sobrevivir snapshot/commit/checkpoint, y retirada/desuscripción ha de ser
atómica con rollback. Falta acreditar congelación/clamping fff.nG/oo, recursión
entre listeners y los emisores autoritativos de PA antes de conectar el handler.

Evidencia local: `.runtime/local/native-1038-eWh.txt` y
`.runtime/local/native-1038-listener.txt` (eWi y eWa originales, javap Java22).
Los cuatro rechazos de Ready identificados pertenecen a breed14/pasivas7096 y
7111. Se mantienen explícitos; instalar un alias o emitir sólo la primera
bonificación ocultaría un fallo de lifecycle.
