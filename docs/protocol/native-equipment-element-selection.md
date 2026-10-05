# Bonos elementales de unidades de equipo

Fuente: eZO/eZP→eWe, fnR.foX, foX.cL/Wi/Wh, fox→kX56/le y vj/vo/vR. Se trata de elecciones persistidas en cada UID, no un sorteo durante la aplicación del bono.

1068 genera hijos eWQ de daño elemental;1069 de resistencia. FIRE/WATER/EARTH/AIR tienen IDs1/2/3/4 y sus características son21/22/23/24 y28/29/30/31. La máscara usa `1 << ID`; los elementos válidos son esos cuatro, no Light/Stasis.

Al crear una unidad mediante grant, `inventory_elements.create` toma la cantidad de la segunda propiedad RAW (So1, truncada a int) y elige sin reemplazo. La selección se guarda atómicamente con el item en SQLite (`inventory_item_elements`, FK UID), se conserva en load/reopen y no se recalcula al equipar. Copias de unidad conservan máscaras; unidades con selecciones diferentes no se mezclan. No se implementó el reroll voluntario de una selección ya existente.

Ambos formatos se generan desde esa misma metadata: kX campo56, mensajele campos requeridos1 damageElements/2 resistanceElements; vj tras cinco opciones ausentes incorpora vo con dos bytes vR, seguido por las dos opciones restantes. El probe Java original acepta y conserva máscaras22/8 en ambos formatos y en foX.

Las unidades antiguas sin metadata siguen como el cliente las recibió: fox pone foX=null, eWe.c sale sin aplicar hijos. Sus bonos1068/1069 son cero; no se rellenan con los primeros tres elementos ni se alteran automáticamente sus elecciones. Los nuevos grants reciben elecciones propias.

Scalar eWQ−1 es un sentinel de copia del efecto disparador en eWW.C, no un bono negativo. En el contexto inicial de equipo sin fLP se convierte en0. Otros negativos, incluido−2, son valores ordinarios; probe original confirma−1→0/−2→−2. No se elimina la guardia independiente de otros tipos de runner no acreditados.

Verificación:12 tests de SQLite/bonos/movimiento pasan; probe Java de formatos, mapping y sentinel pasa. Un foco del motor común con arma2869, snapshot construido fresco, muestra más daño con selección guardada22 que con foX ausente; originales preservados. El primer fixture intentó reemplazar un snapshot instalado y fue rechazado; se corrigió el fixture construyendo actor nuevo, manteniendo intacta la protección de snapshots del motor.

Pendientes: rerun exhaustivo para nuevos conteos y prueba GUI tras despliegue coordinado. No hubo cambios en DB real ni reinicio durante esta implementación. No se afirma que todos los criterios de equipamiento ni todos los otros bonos estén soportados.
