# Equipo al volver del combate

`outside_progression` ya aplica `equipment_stats.effective_character` y `combat_resources` antes de producir el formato 3: conserva PA, PM, PW, iniciativa y vida máxima del equipo seleccionado, sin alterar los objetos persistidos ni curar heridas. Las mismas reglas sirven a retorno normal y abandono. Las pruebas comprueban amuleto 2021 (PA 7, vida máxima +6), retirada (PA 6) y conservación de inventario.

La inspección ejecutable de `eHf.values()[3].fuK()` demuestra que formato 3 contiene XP, posición, combate, características de combate, propiedades, raza, control IA, características públicas, ID, identidad, héroe y downscale. No contiene EQUIPMENT_APPEARANCE ni ACTIVE_EQUIPMENT_SHEET. Insertar allí bytes de apariencia dañaría el codec. El cero detrás de las características es FIGHT_PROPERTIES.

La notificación 12103 es de aptitudes: `cFN.a(ctL)` llama `eQx.ey` y entrega eQJ al actor. La notificación 12996 contiene metadatos de builds eQW. Ninguna debe utilizarse como refresco de equipo. La ruta de equipo comprobada es 12284: ctU.dqw devuelve fpj y cER/dbU.b aplica fpl.a(index,fpj). Reenviarla sin petición también muestra build.saved, por lo que no se agregó un refresco arbitrario.

El reset 13256 publica LEAVE_INSTANCE y limpia mapa/interfaz; dsQ/dsR elimina bLM visuales. En las rutas revisadas no se encontró borrado de fpd/fpl. La causa del slot vacío sigue sin confirmar: falta comparar estado vivo de biB.dqw(), biB.Dj(0) y bIM.tT(characterID) con el modelo del panel. Sin esa evidencia no se atribuye el fallo a borrar inventario. Fuentes: .runtime/local/equipment-return-*.txt e InspectFighterSections.java.
