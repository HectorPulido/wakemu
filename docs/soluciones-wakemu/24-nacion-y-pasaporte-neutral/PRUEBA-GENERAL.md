# Prueba general — nación y pasaporte neutral

**Estado:** lista para la aceptación manual; la neutralidad visual del pasaporte y de la selección todavía requiere observación en cliente. Se corrigió el serializador de entidad; no se modificó el dispatcher ni se declara cerrado el issue.

## Qué verifica

La UI nativa abre `passportDialog` con el comando `/passport`. El frame `ddU` enlaza `pvpLadderEntry` a `bMO.a(personaje,false)`; el getter `nationId` de ese modelo devuelve `fxl.Xt()`, construido desde `personaje.fqe().Xt()`. Por tanto, la aserción del pasaporte es el estado nacional del personaje activo, no una propiedad inferida de su mapa.

El serializador del servidor establece `NATION_ID` y `CHARACTER_LIST_NATION_ID` en `0`, y `PASSEPORT_INFO` en `00`, en layouts reconocidos. La prueba de roster confirmó que `qZ.aG` parsea nación `0`; el locale la asocia con “Neutral”. La captura histórica de selección que mostró Amakna no es una medición de esos bytes actuales.

## Pasos

1. Inicia sesión en el Wakemu local y selecciona un personaje propio existente. Anota exactamente el nombre y lo que muestra la ficha nacional del selector.
2. Entra al mundo y ejecuta `/passport` mediante la consola nativa del cliente. Debe abrirse `passportDialog`, con el control `pvpLadderEntry`; comprueba que la nación sea **Neutral**. Si el inspector del cliente está disponible, registra `pvpLadderEntry.nationId` y exige valor `0`.
3. Cierra la ventana ejecutando `/passport` otra vez o usando Escape. No hagas clic en una X: una prueba instrumentada anterior propagó el clic al mundo y movió al personaje.
4. Cierra sesión, vuelve a iniciar sesión con el mismo personaje y repite los pasos 1–3. Selector y pasaporte deben seguir mostrando Neutral/0.
5. Registra resultado PASS/FAIL con versión de servidor, boot ID, personaje y evidencia visual o payload decodificado. Los logs actuales solo contienen opcode y tamaño: por sí solos no acreditan el contenido nacional de la respuesta.

## Límite territorial

`social.adapt(15984)` vacía únicamente los registros regionales de nación formato 17 y conserva otros tipos. `territory_cells.py` identifica región/mapa para ubicación; no contiene una nación por territorio. Esa normalización no demuestra neutralidad de propietario territorial, gobiernos, NPCs o nombres geográficos. Para cerrar la petición de “lugares sin nación” hace falta una autoridad nativa de propiedad territorial independiente; no sobrescribirla con el número `0` hasta conocer su carrier.
