# General cast diagnostics — 2026-10-08

The accepted `combat_cast` and rejected `combat_cast_rejected` events now record
`cast_diagnostics`, selected native casting-table provenance, resolved flags,
native eligibility details and validation codes. They apply to every class.

Diagnostics include fight/caster/spell/level/cell; the actual evaluated criterion
and result for every conditional table; selected and baseline table values;
AP/MP/WP costs; resolved minimum/maximum, LOS and alignment/free-cell flags;
owner active/passive references and actual caster condition deck; live RANGE,
carry/properties/modifiers; and every fighter state UID/reference/level/source.

The evaluator records results while executing the original condition once.
Logging never performs a second criterion evaluation or RNG draw. Unknown or
ambiguous selection retains a partial diagnostic and does not invent a table.
A rejected target keeps its preflight context on the exception. The diagnostic
callback receives a detached copy; it cannot modify the decision facts.

Read `.runtime/local/logs/game-server.jsonl` locally; do not commit this private
log. Correlate by request_id, fight_id and caster_id. For a report such as
Buscadora through a wall, inspect evaluated criteria and actor_states:
state7757 is Tiro Preciso, state7792 is Precision, state3420 is Esquivo.
Spell7792 is Contact Beacon and is a separate namespace. A matched/no-match
criterion is evidence of requirements at request time, not a percentage of
functional class mechanics. Existing effect traces preserve nested criteria,
retained event origins and producer failures.

Validation: seven focused diagnostics/provenance regressions pass, including
accepted selection, rejected LOS/eligibility, unknown partial selection, JSON
round-trip and exactly one evaluation per conditional table.
