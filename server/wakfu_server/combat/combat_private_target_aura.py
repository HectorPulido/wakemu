"""eYJ-only private faN constructed with actual constructor PN.baf()==null."""
SOURCE = "eYJ.c.PN.baf_null"


def validate_private_target_aura(fight, row):
    private = row.get("native_private_area")
    if private is None:
        return None
    if (
        row.get("effect_class") != 338
        or not isinstance(private, dict)
        or type(row.get("uid")) is not int
        or not 0 < row["uid"] < (1 << 63)
        or type(private.get("uid")) is not int
        or not 0 < private["uid"] < (1 << 63)
        or private["uid"] == row["uid"]
        or type(private.get("reference")) is not int
        or private["reference"] <= 0
        or type(private.get("level")) is not int
        or not -32768 <= private["level"] <= 32767
        or type(private.get("anchor_id")) is not int
        or private["anchor_id"] != row.get("caster_id")
        or private.get("source") != SOURCE
        or private.get("uid") != row.get("area_uid")
        or private.get("native_area_contract") != "faN"
        or private.get("anchor_id") != row.get("target_id")
        or private.get("owner_id") != row.get("target_id")
        or private.get("registered") is not False
        or private.get("creation_callbacks_executed") is not False
        or private.get("uid") in getattr(fight, "native_effect_areas", {})
        or private.get("uid") in getattr(fight, "native_retired_area_managers", {})
    ):
        raise ValueError("Missing exact private native eYJ constructor area")
    return private
