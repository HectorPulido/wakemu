"""Snapshot geometry from the native locator; not damage-event evidence."""


def measure(fight):
    from wakfu_server.combat_ordinary_authority import native_facing

    source = fight.current
    if source is None or source.hp <= 0:
        return dict(nativeFacingActorId=None, nativeFacings={})
    values = {}
    for target in sorted(fight.actors.values(), key=lambda actor: actor.id):
        if target.hp <= 0 or target.team == source.team:
            continue
        try:
            values[str(target.id)] = native_facing(source, target)
        except ValueError:
            values[str(target.id)] = None
    return dict(nativeFacingActorId=source.id, nativeFacings=values)
