"""Explicit operator outcomes, settled by the ordinary combat lifecycle."""
from copy import deepcopy

from .combat_shared import Transition


def finish(fight, runtime, *, account_id, character_id, win):
    """Prepare an isolated terminal state without changing decks or memberships."""
    if type(win) is not bool:
        raise ValueError("Invalid requested combat outcome")
    if fight is None or fight.phase != "active" or runtime is None:
        raise ValueError("Debes iniciar el combate antes de usar este comando")
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
    for member in candidate.actors.values():
        if member.team != winner and not getattr(member, "pve_withdrawn", False):
            member.hp = 0
    candidate.phase = "finished"
    candidate.winner = winner
    candidate._event("finished", winner=winner)
    messages.fight = candidate
    return Transition(candidate, messages, ())
