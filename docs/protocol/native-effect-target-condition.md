GetEffectTarget — token54, eQd->eKb
==================================

Cliente instalado eKb.d llama eII.b(true,caster,target,context4,context3).
Si target implementa eHg devuelve target; eHg extiende amP y el resultado
numérico es Sn() signedlong. No es el caster ni el ID de la fuente del evento.
Si no hay actor resuelto devuelve0. eII.b contiene fallback por contexto ePy
(fyI) o posición aBn+fbX; esos contextos futuros requieren resolución explícita,
no deben convertirse silenciosamente en cero.

El adaptador ordinary proporciona el actor de invocación actual, después de
rebinding del listener/selector. Ausencia explícita invocation.target_id=None
acredita null en ese contexto; ID desconocido o identidad faltante rechaza.
Contextos manuales deben declarar effect_target_absent=True para null probado.
Sin argumentos; selector/argumentos adicionales rechazados.

ProbeNativeEffectTarget ejecuta eKb y eHg reales: caster7/target-8 -> -8,
rebinding99 ->99, targetnull ->0. Tests cubren lo anterior, datos desconocidos
y aridad incorrecta. No validación visual ni reinicio del servidor.
