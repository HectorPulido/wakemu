# Identidades de obstáculos de combate

El UID largo del actor y su afiliación de equipo son distintos del índice byte
`bcN` del obstáculo en el mapa de combate. `big.doV` (línea fuente2332) consulta
`QI.O(actor.bcN())`: si el índice ya pertenece a otro actor, registra el error
«Obstacle de meme id». `QI` mantiene un array de127 entradas; el dominio válido
es0..126. `eGj.bcN` delega al descriptor `eGZ`, mientras `bcM` es independiente.

El bootstrap anterior escribía el equipo en ese índice. Dos monstruos del equipo1
compartían la entrada1 aunque sus UID largos fueran distintos. La corrección
asigna un índice único por Fight, lo conserva en snapshots y lo usa tanto en la
entrada como en actualizaciones. La afiliación del participante sigue intacta.

Verificación: probe original `ProbeNativeObstacleIds.java` registra objetos QK en
QI:2/8 monstruos con índices distintos permanecen identificables; dos objetos con
índice1 reemplazan la misma entrada.33 pruebas Python de bootstrap/actores/invocaciones pasan,
incluidos grupos2/8 con UID negativos grandes. No constituye prueba visual del
cliente después de desplegar.

Las identidades permanecen reservadas mientras el actor/cadáver exista en el Fight;
no se reciclan durante retiradas con efectos tardíos. El límite127 debe rechazarse
antes de crear otra entidad, sin alterar el roster original.

La creación307 también transmitía el equipo en `eHD.bgW`/`vJ.Uj`. El
consumidor original `eHD.a(eGj,eGj)` llama `eGj.M(bgW)`; ahora el descriptor
recibe el índice reservado del actor nuevo. `specification.team` sigue siendo
la afiliación real en la sección posterior del mismo descriptor.

Límite pendiente: la prueba de entrada completa Esfera5345 rechaza una autoridad
de área no acreditada; esta corrección no elimina ese guard ni acredita su GUI.
