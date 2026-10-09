# Otorgamiento temporal de hechizos: familia 649

Fuente offline: `eVi` identifica el ejecutor `eWn`. `eWn.C` evalúa barra byte,
casilla short, referencia int y nivel short. El nivel -1 usa el nivel efectivo
del receptor. `fyH.gub.j` crea el hechizo; `fyG.dg(fyG.awe())` usa la referencia
como UID. `fyR.f/b/c` y `fzf.aW/aX` gestionan registro y habilitación temporal;
no hay contador de referencias. La retirada restaura el atajo previo en el
cliente mediante `eWn.bbR`.

`ProbeNativeSpellGrant.java` ejecuta el serializador nativo: referencia 5345,
nivel -1, barra 2 y casilla 0 producen AdditionalDatas
`50e12970ffffffffffffffffff01980102a00100`.

El catálogo separado `native-spell-casting.json` contiene 4.143 referencias
instaladas aNr/bPS/fyF/fyP, con máximos nativos, raíces por nivel, costes,
categorías y tablas condicionales completas de alcance/LOS/celda libre.
`ExportNativeSpellCasting.java` es reproducible offline. No sustituye el
inventario de 722 hechizos de clase.

La entrada común acepta UID plano sólo si el registro temporal del propio
actor conserva esa referencia. Evalúa el nivel concedido, selecciona la tabla
fyP completa y rechaza ramas ambiguas o desconocidas que puedan alterar la
tabla. Usa costes vivos por categorías y las comprobaciones comunes de
terreno y recursos. El paquete de casteo conserva UID y nivel nativos.
Retirar el otorgamiento invalida la petición siguiente.

El exportador usa `bPS.IP`, que adjunta los efectos mediante `bPS.c(aNr)`;
construir `bPK(bPS.d(raw))` omite esa etapa y genera raíces vacías. Una prueba
compara las raíces de 6266 con el catálogo auditado y exige raíces en 5345.
El constructor nativo `bPO(bPK,short,long,eGj)` aplica `Math.min(nivel,Fq)`.
`ProbeNativeGrantedLevel.java` confirma 5345/5624 pedidos a200 →1 y3909 →200.
El grant conserva el nivel raw en AdditionalDatas pero registra ese nivel
clampado para el casteo. Se exportan todos los niveles nativos (máximo300).

`build_granted_spell_references.py` deriva167 referencias de todas las649 de
los catálogos de hechizos y estados. Verifica que el parámetro referencia no
escala; repetir con los árboles exportados no añade referencias. El cierre
contiene2589 efectos,2123 adicionales al catálogo común anterior. Se combina
una sola vez en el catálogo estático precompilado, conservando la validación
de conflictos. El campo `fyF.elO` de las4143 referencias acredita el tipo11/25
y protección del contenedor de hechizos temporales.

Verificación focal: 12 pruebas pasan (5 de granted-cast y7 de máximos). Una
prueba ejecuta la definición649 real313108 mediante dispatcher y condiciones
comunes, luego castea3909 por la entrada de servidor con sus raíces nativas,
confirma efecto de máximo eWN y UID3909/nivel20 en12588, conserva el original
y rechaza tras retirada. La focal independiente también prepara7794 con6
paquetes/4outcomes.5345 alcanza la siguiente familia no implementada307.

La ruta ampliada está detrás de `WAKFU_NATIVE_GRANTED_CAST=1`, default0 hasta
integración controlada. Esto no acredita todos los manejadores ni el uso GUI.
La innata Xelor6755 retiene313103 para el evento1028: entregar sólo1003 no
instala los grants. La producción de1028 sigue pendiente de evidencia nativa;
la prueba de la familia no finge que Ready ya lo emita.
