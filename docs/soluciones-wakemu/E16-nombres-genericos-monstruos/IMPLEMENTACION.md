# Implementación E16 — 2026-10-05

`combat_monster_world.world_actor` resuelve por defecto el nombre de la referencia individual en el catálogo del servidor. `spawn_monster` usa la misma regla; `spawn_group` ya no acepta un nombre compartido para todo el roster. Se eliminaron los defaults «Monstruo local» y «Grupo local». Los IDs, referencias y composición del grupo se conservan.

La ruta compartida cubre aparición, plantación, crecimiento, respawn y retorno al mundo. Los nombres proceden del catálogo actual en español; no se afirma negociación de idioma ni traducción dinámica. Referencias sin nombre siguen rechazadas, sin inventar etiquetas de depuración. Las17 referencias vacías requieren completar fuentes antes de publicarlas; los nombres explícitos individuales siguen disponibles para NPC especiales.

Pruebas: grupo mixto Wonejo5525/Dragonito vivaz4168, nombres distintos y roster completo en cada actor, publicación repetida, rechazo de nombre ausente sin registrar grupo, además de grupos/consola/plantación. Validación visual en partida y otros idiomas pendiente. No declarar el cierre integral hasta acreditar esos recorridos.

## Prueba visual del 6 de octubre

La ficha aportada por el usuario muestra «Tofu», nivel8: el nombre individual de referencia4 coincide con el catálogo español. No acredita todavía el nombre tras reconexión ni otras referencias. El combate que inició después expuso una regresión independiente, documentada en00/REGRESION-COMBATE-2026-10-06.md; no atribuirla a la serialización del nombre ni declarar cerradas las rutas de combate.
