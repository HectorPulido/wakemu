# Identidad del lanzador del efecto desencadenante

Fuente instalada: lexer eQb token176 (`GetTriggeringEffectCasterIsSameAsCaster`), parser eQd crea eLL, constructor sin argumentos. eLL.a exige contexto Qe; compara por identidad de objeto Qe.bbb() con eII.aW(contexto). eII.aW devuelve el lanzador del eZR fuente seleccionado por eII.aU, o null si no hay fuente. amb.b interpreta resultado0 como verdadero y−1 como falso.

El adaptador común resuelve las identidades registradas al mismo objeto Actor del roster de la transacción. No compara contra el objetivo del listener, un ID de hechizo ni un valor centinela. Si la fuente no existe o su lanzador es null y el lanzador actual existe, devuelve falso. Un descriptor incompleto o una identidad no registrada permanece desconocido y se rechaza.

`sniffer/java/ProbeNativeSameTriggerCaster.java` prueba el original: ambos null, fuente ausente, mismo objeto, otro objeto, lanzador de fuente null y contexto distinto de Qe; seis casos pasan. En producción el adaptador recibe siempre el lanzador real registrado; el caso ambos null sólo pertenece al probe original.

Incidente PruebaYopuka20:12403 rechazaba este criterio; la expiración automática repetía el fin de turno y dejaba escapar UnknownCondition, cerrando el socket. La frontera ahora publica el fin sólo tras completar las reacciones; también protege proveedores de fin sin proveedor de inicio. La expiración rechazada reanuncia12053/13482/13420 del turno intacto y rearma el reloj. No avanza turno ni fabrica efectos o recompensas. El rechazo manual sólo reanuncia un turno propio activo sin barrera ACK pendiente.
