# Alturas usadas al lanzar ataques

La altura del lanzador y del objetivo no es siempre seis. `eGj.bcK()` delega
en la definición del actor. Para jugadores, `eGE.bcK()` devuelve seis.

Los monstruos ordinarios usan `blj`, que sobrescribe `eGC.bcK()`. Su constructor
guarda el parámetro doce como un byte en `iul`; `bbo` obtiene ese parámetro de
`aMb.css()`. Por tanto, usar la constante de la clase base `eGC` para todos los
monstruos pierde información original.

El exportador `ExportActorCharacteristics.java` conserva esta altura como
`npc_profiles[referencia].native_los_height`, y la altura de jugador como
`default_actor_los_height`. Se añadieron ambos campos al catálogo existente sin
reemplazar sus características ni sus curvas. Ejemplos: monstruo 5525, altura
cuatro; Wonejo 3646, altura tres. Las 2.874 definiciones tienen alturas entre uno
y veinticinco.

Estos son datos de entrada para el cálculo nativo de línea de visión de
lanzamiento (`fcr`); no acreditan por sí solos la implementación del recorrido
del rayo ni autorizan tratar una línea desconocida como despejada.
