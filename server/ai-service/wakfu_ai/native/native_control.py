"""Read current control from the installed embedding engine, without identity edits."""


def effective_server_controlled(fight, actor):
    from wakfu_server.combat_effective_control import (
        effective_server_controlled as query,
    )

    return query(fight, actor)


def effective_affiliation(fight, actor):
    from wakfu_server.combat_effective_control import effective_affiliation as query

    return query(fight, actor)


def effective_input_owner(fight, actor):
    from wakfu_server.combat_effective_control import effective_input_owner as query

    return query(fight, actor)
