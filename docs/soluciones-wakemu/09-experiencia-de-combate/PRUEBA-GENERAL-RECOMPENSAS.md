# Prueba general: XP, nivel, kamas y drops

Imagen activa: `9af0658c4e5db5da40debb6ba8c656f248bc10397fb6055a03ae76f215039a28`.
Migraciones001–048 aplicadas. Gate base de imagen259/259; corrección posterior de snapshot HP validada con dos recorridos completos por socket, combate/12925/reconexión aprobados. No se cambiaron hechizos, daño, turnos ni IA.

La política de drop activa vuelve a versión1, multiplicador×1; XP/kamas también×1. Se corrigió el comando inválido para Tofu nivel1: se usa Mimic dulce4196 nivel1,1PdV, cuyo drop12325×3 tiene tasa base100% y no requiere aumentar la probabilidad.

1. Entra con un personaje de nivel1, o crea uno para esta prueba. Abre Personaje e inventario y anota nivel, XP, kamas y número de unidades del objeto12325.
2. En general escribe `!mob 4196 1 1`. Esperado: aparece un Mimic dulce nivel1.
3. Atácalo, pulsa Listo y derrótalo usando los ataques disponibles. Esperado: termina sin desconexión; el resumen muestra XP positiva, kamas y 3 unidades del objeto12325. Con personaje recién creado, sabiduría0 y XP0, recibe XP positiva suficiente para nivel2 y25–45kamas; la XP exacta depende de la sabiduría efectiva del personaje.
4. Cierra el resumen y abre Personaje/inventario. Esperado: nivel/XP coherentes con el resumen, kamas sumadas y 3 unidades más; puedes caminar. Si el inventario ya estaba abierto, su saldo se actualiza sin cerrarlo.
5. Repite `!mob 4196 1 1` y otra victoria. Esperado: se suman las nuevas recompensas una sola vez; aparecen otras3 unidades y conservas la conexión.
6. Cambia de personaje, vuelve y reinicia el cliente. Esperado: nivel, XP, kamas y objetos conservados, sin duplicaciones; puedes caminar y abrir inventario.

La automatización cubre adicionalmente bolsas llenas, overflow durable, bootstrap temporal, reclamación13993, retry y rollback. No se exige llenar bolsas manualmente para volver a comprobar estos casos.

Pendientes del sistema de drop: criterios complejos, clasificación de mazmorras, tablas externas y semántica de rollMax/filas repetidas. Esta prueba acredita el ciclo general disponible, no cierra esos alcances sin evidencia.
