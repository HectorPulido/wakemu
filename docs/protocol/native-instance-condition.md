GetInstanceId token58/eKB — origen del campo nativo
==================================================

eKB.d resuelve eII.l: primer eGj en caster, después target y contexto.
Devuelve eGj.arM, campo aJo signedlong; eGj.fE(long) escribe aJo.
No utiliza Fight.id ni la columna SQLite instance_id.

Origen confirmado por bytecode: rE.aG lee XC:int,XD:int,XE:short,Vp:long,
XF:byte,etc. eGt.zm llama eGj.fE(rE.Vp). combat_actor POSITION escribe
character['map_id']/monster['map_id'] en ese mismo campo long.
OrdinaryActorAuthority expone native_instance_id; adapter lo transmite a
ConditionActor. No hay valor por defecto; ausencia conserva error explícito.

ProbeNativeInstanceCondition lee POSITION nativo y fE/arM/eKB: caster1385,
targetfallback527,signedlong-4000; contexto ausente lanza alA. Pruebas cubren
prioridad caster, fallback target, datos desconocidos y aridad incorrecta.
Contextos adicionales fya/SN/fwL/fpw necesitan su propia autoridad explícita.

El fixture de transacciones ahora proporciona map_id1134 como propiedad
POSITION. Su ausencia previa no se sustituyó por Fight.id78 ni0.
Ready real5051 supera este criterio pero siguiente bloqueo es familia649.
Sin reinicios ni modificaciones en datos de usuario.
