# Correcciones de abandono

El cliente oficial local documentó BufferUnderflow en csZ.dp al volver de los combates 745421918 y 436535014. Los paquetes 13046 emitían ID y blob, pero el codec exige ID, longitud i16 y blob. Todos los emisores ahora comparten combat_world_refresh.actor_refresh. Java nativo confirmó ambos blobs (formatos 3 y 17).

Además, cvF.huN=true no garantiza cerrar la interfaz: aUH remueve el jugador y, si buH.dLM devuelve true porque queda un único bando, retorna antes de limpiar frames/timeline. Aun así cbj envía 12925, causando un retorno aparente en servidor con interfaz vieja.

El abandono ahora emite cvF normal huN=false con NPCs ganadores y propio bando perdedor, lo que ejecuta cleanup completo. La FSM propia conserva finished/winnerNone, checkpoint aborted, ninguna recompensa y grupo vivo liberado. Este resultado nativo representa rendición; no añade un reporte de victoria ni inventa penalización de HP. El callback 12925 contiene huO, indicador de derrota, no spectator. Se exige flag1 para este abandono.

La verificación Java real leyó listas winnerNPC=-200/loserOwn=1 y generó coQ con loss1. Pruebas unitarias validan recibo único, no recompensas, heridas conservadas y ownership. Verificadores: sniffer/java/VerifyWorldActorRefresh.java y VerifyAbandonFinalization.java. Evidencia previa se conserva en review_history del JSON. GUI tras desplegar está pendiente; no se reinició ningún servicio ni cliente.
