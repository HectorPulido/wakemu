"""Publish settled mission notifications after native combat cleanup.

Native cEH queues objective updates on the live fight executor. Sending them
behind terminal cleanup can orphan that queued work. The official Rii capture
publishes them after the authenticated 12925 callback instead. Persistence and
reward settlement still happen at victory; a fresh login uses its authoritative
quest bootstrap if the original socket disconnects before returning.
"""


def defer(fight, account_id, generation, character_id, packets):
    packets = tuple(packets)
    if not packets:
        return
    pending = dict(getattr(fight, "post_combat_progression", {}))
    row = (fight.id, account_id, generation, character_id, packets)
    previous = pending.get(account_id)
    if previous is not None and previous != row:
        raise ValueError("Conflicting settled combat progression delivery")
    pending[account_id] = row
    fight.post_combat_progression = pending


def after_return(fight, account_id, generation, character_id):
    row = getattr(fight, "post_combat_progression", {}).get(account_id)
    if row is None:
        return ()
    if (row[0], row[1], row[3]) != (fight.id, account_id, character_id):
        raise ValueError("Foreign settled combat progression delivery")
    if row[2] != generation:
        # The replacement connection already loaded authoritative quest state.
        # Do not replay its predecessor's notifications or obstruct its return.
        return ()
    return row[4]
