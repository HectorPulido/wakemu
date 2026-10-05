# Orden nativo de objetivos: banderas14/26 y bandera gráfica3

El cliente eVl define14=SORT_TARGET_BY_DISTANCE_ASC y26=DESC. No son
ordinales del enum: fLK devuelve sus IDs. El escaneo exacto de referencias
GETSTATIC encuentra como único consumidor funcional faK.a; faF/faG comparan
PV.baM().cG(x,y), distancia Manhattan int32 al punto suministrado del efecto,
ignorando Z. faH reúne y filtra los actores, llama List.sort estable y luego
aplica fKH como byte firmado: sólo valores positivos recortan la lista.
La prioridad de faK es8(vida asc),25(vida desc),14(distancia asc),26(desc).

combat_target_ordering aplica14/26 después de la selección nativa del
resolvedor. Conserva empates en el orden recibido y no introduce un desempate
por UID. ExportNativeTargetOrdering acredita375 definiciones sobre178337,
incluyendo fKH y la identidad exacta de clase/banderas. La referencia370600
usada por Tromba tiene26 y máximo-1. Las identidades ausentes/conflictivas se
rechazan. Las banderas8/25 combinadas con distancia se rechazan hasta auditar
sus snapshots de vida: no se ignora su prioridad. Los límites de definiciones
sin14/26 y el orden implícito de otras áreas siguen siendo una auditoría aparte.

La bandera3=DONT_DISPLAY_ZONE tiene como único consumidor funcional aJs.a.
Su rama recorre definiciones de un hechizo y omite el dibujo de la zona cuando
la bandera está presente; no cambia ejecución, cálculo ni eventos. El validador
genérico de grupos permite3 conservando la bandera en la definición; no la
borra. Otras banderas desconocidas siguen rechazándose.

ProbeNativeTargetOrdering invoca los métodos nativos privados de faH y
exporta12 casos de14/26/prioridad combinada, empates y límites-1/0/1/3.
Cinco pruebas específicas y16 combinadas pasan. Se prueba además overflow
int32 nativo y rechazo de prioridad de vida desconocida. Reproducir referencias:
FindNativeFieldConsumers client/lib/wakfu-client.jar eVl rwW/rwA; javap -c -p
sobre eVl,faK,faF,faG,faH,aBn,aJs. ExportNativeTargetOrdering reproduce
native-target-ordering.json; ProbeNativeTargetOrdering reproduce su fixture.

Historial real de Tromba6469 con1003: niveles5/200 crean41 paquetes de inicio
con estados reales7916/7919. Primero detenidos por26 en370600; tras orden
nativo avanzan a bandera gráfica3 en416555. Ambos rechazos conservan fuente,
recursos y UID originales. Próxima repetición incorpora3; no se ha afirmado
éxito de daño antes de observarlo.
# Regresión de entrada real

`native-cone-tromba-start-final-casts.json` valida el camino común en niveles5/200, con fuentes estables y rollback conservado: daño6 y desplazamiento2 en nivel5; daño12, muerte y fin en nivel200. Los modos de estado proceden de las raíces reales y replay1003 normal, sin instalar estados sintéticos ni saltar condiciones. El guard de desplazamiento admite14/26 porque su único consumidor es faK; conserva las banderas y sigue rechazando16 desconocido para esa familia. La prueba focal `test_resolver_order_flags_preserve_displacement_and_unknown_rejection` pasa. Es una validación offline de entrada legal, no validación GUI ni cobertura total de la raza.
