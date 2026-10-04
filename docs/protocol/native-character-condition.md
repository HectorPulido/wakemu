# IsCharacter

El token eQb301 construye eND. El criterio selecciona caster por defecto o target explícito y comprueba eHg.a(eHh.pNi), cuyo enum es CHARACTER. PLAYER_CHARACTER y NON_PLAYER_CHARACTER pertenecen a esa categoría; no equivale a is_player.

El bytecode eGj.a(eHh) delega en eHh.CHARACTER.a(tipo). El adaptador actual puede acreditar CHARACTER para actores cuya autoridad identifica eGj. Para otros tipos mantiene desconocido hasta disponer de su implementación nativa.

Evidencia local: .runtime/local/native_is_character.txt, native_character_kind.txt y native_has_state_e_gj.txt. Prueba: test_character_kind_includes_npc_and_preserves_unknown.
