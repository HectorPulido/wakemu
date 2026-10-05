# Selectores de equipo y flags REP de la fuente

La segunda Sacudida sobre un actor con Sacudido8913 activaba408737→397253 y rechazaba GetTeamId("triggeringCaster"). El validador solo aceptaba caster/target. Original eLx delega en eII.a: admite triggeringCaster/triggeringTarget y casterController, compara el bcM firmado del objeto real y devuelve−1 para objeto nulo o selector desconocido. La autoridad ahora resuelve los actores de la fuente del evento, separados del listener rebindeado. Una identidad no registrada permanece desconocida; no se deduce del caster del listener.

La misma cadena necesitaba IsTriggeredByEffectWithREP(28). Original token347→eOY toma la fuente eII.aU, convierte el argumento long a int, busca eVl.SM y consulta eZR.a(flag), que delega en los flags del PK/eVn de esa fuente. No consulta flags del listener. Fuente nula devuelvefalse. Los eventos transportan los native_effect_flags acreditados; metadata desconocida se rechaza solo cuando el criterio la necesita.

ProbeNativeTeamId.java: default/target y triggeringCaster/Target, selector desconocido y fuente nula pasan con originaleLx/eII. ProbeNativeSourceREP.java: flag presente/ausente/fuente nula y conversiónlong-int pasan con originaleOY/eZR. Enumeración nativa:1..6 y8..37 (7 no existe). Argumentos booleanos/números como selector GetTeamId se rechazan.

Este cambio no modifica el carrier310 ni su opcode de entrega. La presentación de estados en GUI sigue siendo una verificación distinta.

Validación de entrada común terminada: doce variantes4780/4783/4778 a20/200 normal/crítico, más segundaSacudida sobre el mismo NPC en los cuatro casos4780. El NPC4085 nivel23 tiene530HP nativos; sobrevive a ambos daños. CosteAP6→4→2,8913 previamente activo,Concentración acumulada y rollback del original verificados. Unidad final PASS en30.246s; log .runtime/local/yopuka-repeat-current.log. No certifica aún interfaz tras despliegue.
