"""Explicit operator outcomes, settled by the ordinary combat lifecycle."""
from copy import deepcopy

from wakfu_server.combat_shared import Transition


def finish(fight, runtime, *, account_id, character_id, win):
    """Prepare an isolated terminal state without changing decks or memberships."""
    if type(win) is not bool:
        raise ValueError("Invalid requested combat outcome")
    if fight is None or fight.phase not in ("placement", "active", "finished"):
        raise ValueError("Debes iniciar el combate antes de usar este comando")
    if runtime is None:
        from wakfu_server.combat_abandon import placement_runtime

        runtime = placement_runtime(fight, None)
    actor = fight.actors.get(character_id)
    if (
        actor is None
        or not actor.controlled
        or actor.owner_id != account_id
        or getattr(actor, "pve_withdrawn", False)
    ):
        raise ValueError("El personaje no participa en este combate")
    teams = {
        a.team for a in fight.actors.values() if not getattr(a, "pve_withdrawn", False)
    }
    if teams != {0, 1}:
        raise ValueError("El combate requiere dos equipos")
    candidate, messages = deepcopy((fight, runtime))
    winner = actor.team if win else 1 - actor.team
    if win and getattr(candidate, "rift_wave_state", None) is not None:
        # Administrative victory is a real explicit operator outcome, never
        # evidence that forty survival rounds or unplayed waves were earned.
        candidate.rift_wave_state["outcome"] = "administrative_victory"
        candidate.rift_wave_state["pending_wave"] = None
    for member in candidate.actors.values():
        if member.team != winner and not getattr(member, "pve_withdrawn", False):
            member.hp = 0
    candidate.phase = "finished"
    candidate.winner = winner
    if fight.phase != "finished" or fight.winner != winner:
        candidate._event("finished", winner=winner)
    messages.fight = candidate
    return Transition(candidate, messages, ())
