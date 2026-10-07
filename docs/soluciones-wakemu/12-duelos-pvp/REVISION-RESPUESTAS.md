# Duelos amistosos: solicitud y ciclo autorizado

## Solicitud nativa comprobada

`cWb.CHARACTER_CAST_DUEL_FIGHT_ACTION` acción8 usa cWi. Su rama `fcz.rVj` se ejecutó y devuelve **DUEL**; `cWi.run` crea **coS/12117**, categoría3. Encoder ejecutado con objetivo12345 en−4,0,0: cuerpo20bytes **i64 objetivo, i32 x, i32 y, i16 z, byte autolock, byte modalidad (default1)**. No atribuir al último byte otra semántica sin consumidor. [Fixture y hash actual](probe-solicitud-desafio-nativa.json).

El dispatcher no atiende12117. 13241 es unirse a combate existente; no sustituye desafío ni demuestra consentimiento. `cWi.run` aplica distancia local<=25 mediante ala.c, pero la unidad/regla autoritativa aún necesita cotejo: no fijar25casillas por esa sola comparación. Validar posición del objetivo desde sesión, nunca confiar en las coordenadas declaradas.

## Reglas respondidas

Desafío amistoso, aceptación obligatoria; al terminar se restaura vida, sin teletransporte ni recompensas. Quien se desconecta pierde y conserva mapa/posición. No se usa progreso ecológico ni premios PvE para este tipo de encuentro. La frase «xp o duelo» del usuario se interpreta por el contexto como ausencia de recompensas; no crea otro modo competitivo.

## Solución concreta y barreras

Crear invitación con IDs de ambas sesiones/personajes, generaciones, ubicación/mapa/instancia y caducidad. La aceptación debe revalidar ambos leases, disponibilidad y posiciones, consumir invitación una sola vez y crear **dos equipos de jugadores** en Registry compartido. No llamar al ataque NPC ni crear un COMBAT_GROUPS para jugadores. Rechazo/cancelación/timeout no cambian salud o ubicación.

Fijar modoDUEL en encuentro y excluir las rutas `combat_rewards`/muerte PvE desde el inicio. El cierre registra ganador/perdedor una vez, restaura salud conforme al máximo efectivo autoritativo y conserva origen individual. 12925 limpia cliente, no decide de nuevo el ganador ni otorga premios. Desconexión resuelve derrota aunque no haya12925; reconexión carga salud/posición ya confirmadas. Bloquear terceros/no consentidos salvo contrato acreditado.

## Límites pendientes

La invitación y respuesta están cotejadas, pero no se encontró un opcode nativo separado de cancelación/timeout ni una semántica de timeout. El modo soportado por la nueva política local es el byte default1; modalidad2 de arena queda fuera. No se ha validado visualmente el menú ni el layout final del resultadoDUEL. Las pruebas de hechizos siguen reservadas a otra sesión; este cotejo no las ejecuta.

## Invitación, consentimiento y cancelación cotejados

Servidor→objetivo **13179/cve**: i64 personaje iniciador + byte modalidad. `ckR` resuelve ese actor, rechaza si está ignorado o ausente (Away) y abre diálogo; modalidad2 usa texto de arena, otras usan invitación general. La invitación sintética12345/modalidad1 fue aceptada por parser. Mantener modalidad1 del desafío observado; no inventar enums adicionales.

Cliente→servidor **13520/coR**, categoría3: i64 **personaje iniciador**, byte aceptación, byte **autolock** tomado de bWD.lzc. Encoder ejecutado para sí/no con autolockfalse; ambos cuerpos10bytes coinciden. No confundir ese i64 con fight_id ni invitation_id. El callback vuelve a comprobar actor visible antes de emitir aceptación; esa comprobación cliente no sustituye revalidación del servidor.

Servidor→cliente **12708/cvd**, byte causa:0 desconocido;1 rechazado;2 jugador no encontrado;3 otra invitación;4 iniciador canceló;5 sin combate pendiente;6 iniciador no disponible;7 creación imposible. `ckQ` muestra strings nativos respectivos; parsers0–7 probados. No se encontró código específico timeout ni se inventa8. [Fixtures y consumidores](probe-consentimiento-y-cancelacion.json).

13520 no transporta nonce: correlacionar con la **única invitación pendiente** de esa sesión destinataria y ese iniciador, validar generaciones/expiry y consumir de manera atómica. Probar respuesta tardía después de cancelar y crear otra con el mismo par; no afirmar que un UUID interno resuelve por sí solo esa ambigüedad. Puede requerir barrera temporal/política de no sustituir una invitación hasta drenar su cierre, que debe validarse con UI y latencia.

### Rechazo reciente y sentido inverso — 2026-10-07

El guard de 60 s tras respuesta para la misma dirección (mismo desafiante y destinatario) es una política local configurable, no un cooldown demostrado como regla nativa. Está justificado como barrera conservadora porque 13520 contiene el personaje iniciador y sí/no/autolock, pero ningún ID de invitación: una respuesta repetida del par puede coincidir con una invitación nueva del mismo par. El 12708 con causa4 (`initiatorCancelled`) es un mensaje servidor→cliente según el codec/consumidor `ckQ`; no se encontró una solicitud cliente→servidor de cancelar el desafío que sirva como ACK de cierre del modal.

Por eso no se elimina la cuarentena basándose solo en el intento observado 21 s después del rechazo. La invitación inversa B→A no comparte esa clave dirigida; debe funcionar inmediatamente mientras la repetición A→B siga protegida. Se añadió `test_same_direction_quarantine_does_not_block_immediate_reverse_challenge` para fijar ambas condiciones. La política por defecto actual queda explícita como decisión local; cualquier reducción requiere medir la latencia/duplicación del cliente y mantener la barrera anti-respuesta obsoleta.

12117/13520 todavía carecen de handlers en el dispatcher. La autoridad fuente ya persiste consentimiento, roster opuesto y settlement sin recompensas; el resultado restaura HP y la ubicación guardada. El gate PostgreSQL es aislado y no demuestra integración de red/GUI ni la presentación visual de salida. No se inyectaron paquetes ni ejecutaron hechizos.
