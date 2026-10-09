"""HP0 runner eligibility from actual fighter status and virtual bcd policy."""
from .combat_ordinary_death import owned_fighter_guards, corpse_gate_bypassed


def runner_target_life_eligible(fight, actor, effect, *, invocation=None):
    """Return the proven eZR corpse decision; unknown status is an error."""
    if actor.hp > 0:
        return True
    if actor.hp != 0 or fight.actors.get(actor.id) is not actor:
        raise ValueError("Invalid native runner target resource/identity")
    guards = owned_fighter_guards(fight, actor)
    if any(type(guards.get(key)) is not bool for key in ("baG", "baK")):
        raise ValueError("Missing actual native HP0 runner target status")
    if not (guards["baG"] or guards["baK"]):
        return True
    return corpse_gate_bypassed(effect, fight=fight, invocation=invocation)


def verify_runner_target_life(fight, actor, effect, *, invocation=None):
    """Do not substitute numerical HP for native PV.baG.

    The existing contexts attest all other executable guards. Only HP0 needs
    this additional actual status proof; ordinary positive-HP callers retain
    their existing context contract. Unknown dynamic bcd remains unknown.
    """
    if not runner_target_life_eligible(fight, actor, effect, invocation=invocation):
        raise ValueError("Native runner does not bypass actual corpse guard")
