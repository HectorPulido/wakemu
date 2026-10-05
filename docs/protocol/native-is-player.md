# IsPlayer — criterio nativo común

Token eQb336 → eQd → eOI. Acepta cero o un string, usa target por defecto y
resuelve eII.a con contexto actual. Consulta eHg.a(eHh.pNj): PLAYER, distinto
de CHARACTER y del criterio IsChallenger que también acepta COMPANION.
Devuelve falso ante actor nulo o selector desconocido. El motor conserva error
cuando falta autoridad, y devuelve falso cuando conoce la ausencia de target.

Integración en combat_conditions reutiliza ConditionActor.is_player, ya
producido por la autoridad ordinaria. No infiere jugador desde equipo/raza.
ProbeNativeIsPlayer.java contrasta seis casos originales (default, caster,
player, NPC, companion, null/unknown); PASS. Dos regresiones específicas y la
suite de condiciones: 28 pruebas PASS. Sin auditoría pesada ni validación GUI.
