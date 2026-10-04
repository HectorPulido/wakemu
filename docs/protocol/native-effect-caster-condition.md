# GetEffectCaster

Token eQb53 construye eJZ. Su método d recibe el caster en el primer argumento y devuelve amP.Sn; no lee el target ni busca automáticamente un invocador. No admite parámetros. Bytecode guardado en .runtime/local/native_get_effect_caster.txt.

El evaluador común usa ConditionActor.actor_id del caster actual, por lo que también respeta el rebinding que haya realizado el contexto de evento. Identidad desconocida se rechaza. El cliente devuelve cero para caster nulo/no amP; ese contexto especial todavía no está acreditado por este adaptador.

Prueba: test_effect_caster_is_current_criterion_actor_identity en server/tests/test_combat_conditions.py.
