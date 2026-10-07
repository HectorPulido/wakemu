"""Resolve registered creature ownership from its native creation record."""


def registered_source(actor, registration):
    source = getattr(actor, "native_summon_source", None)
    if not isinstance(registration, dict) or not isinstance(
        registration.get("authority"), dict
    ):
        raise ValueError("Missing complete registered summon authority")
    authority = registration["authority"]
    if (
        type(actor.id) is not int
        or not 0 < actor.id < (1 << 63)
        or registration.get("actor_id") != actor.id
        or not isinstance(source, dict)
        or authority.get("is_summon") is not True
        or authority.get("is_player") is not False
        or type(source.get("ref")) is not int
        or type(source.get("level")) is not int
        or authority.get("breed_id") != source["ref"]
        or authority.get("native_real_level") != source["level"]
        or source["level"] != actor.effective_level
        or registration.get("caster_id") != source.get("caster_id")
        or registration.get("controller_id") != source.get("controller_id")
        or type(source.get("direction")) is not int
        or not 0 <= source["direction"] < 8
        or type(authority.get("native_instance_id")) is not int
    ):
        raise ValueError("Missing complete registered summon authority")
    return dict(
        source,
        id=actor.id,
        team=actor.team,
        x=actor.position[0],
        y=actor.position[1],
        z=actor.position[2],
        map_id=authority["native_instance_id"],
    )
