# HasState con nivel exacto

`eME.a` usa `eHg.kY(stateId)` cuando falta el nivel y `eHg.v(stateId, level)` cuando existe. `eGj.v` recorre el gestor de estados; al primer `fyW.guI` coincidente devuelve si `fyW.cmZ` es igual al nivel solicitado. No aplica umbral ni continúa buscando otro duplicado. `eGj.df` usa el mismo valor para GetStateLevel.

Evidencia local: `.runtime/local/native_has_state_e_me.txt` y `native_has_state_e_gj.txt`. Implementación: `server/wakfu_server/combat/combat_conditions.py`. Prueba: `test_has_state_level_is_exact_first_match_not_threshold`.

El contexto necesita la lista ordenada de niveles de estados actuales. La ausencia de ese contexto se rechaza; no se transforma en falso. Esta entrega admite niveles enteros literales no negativos, con actor caster por defecto o selector explícito caster/target. Expresiones numéricas más amplias siguen pendientes.
