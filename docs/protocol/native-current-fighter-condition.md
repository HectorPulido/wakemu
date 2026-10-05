# Identidad del combatiente activo

`GetCurrentFighterId()` se resuelve en el cliente por eQb token107 → eQd → eJJ. eJJ obtiene el combate mediante eII.o: devuelve0 si no hay combate o si fem.bhI() es falso; en caso contrario devuelve fem.bhJ(). SU delega esa identidad al gestor de turnos, o a su identidad explícita cuando brZ está activo. No lee el caster ni el target del efecto.

La implementación común recibe `ConditionContext.current_fighter_id` del preview: la identidad de `Fight.current` durante un turno activo, y0 fuera de él. Un contexto sin esa autoridad rechaza el criterio. Se valida signed-long y ausencia de argumentos. El evaluador mantiene validación de todas las ramas.

Validación: 31 pruebas de condiciones e inventario/fecha pasan; cubren identidad negativa de NPC, cero explícito, autoridad ausente y argumentos inválidos. La validación integral del ciclo de turno y de los pasivos queda separada de estos controles. No se afirma verificación gráfica.
