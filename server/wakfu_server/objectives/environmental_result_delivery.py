"""Pure, source-qualified native result publication; never reward settlement.

The caller joins a durable publication outbox row to its event, participant and
an immutable native result profile. Missing profiles intentionally produce no
13263 packet. In particular, a contribution score is not a reward-list index.
"""
from .environmental_results import result_packet


def _integer(value, name, minimum=0, maximum=2**63 - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid environmental result " + name)
    return value


def _authority(value, name):
    if type(value) is not str or not value.strip():
        raise ValueError("Missing environmental result " + name + " authority")


def plan_result_delivery(delivery, view, *, account_id, character_id):
    """Return one immutable packet plan, or None without qualified authority.

    ``delivery`` is a durable outbox row (key, kind, instance, revision, owner).
    ``view`` is the same event/profile snapshot as the World publication.
    ``view['native_result']`` is an optional SQL projection, not a mutable game
    configuration dictionary. Its exact contract is:

    - profile_key/version/instance_id/account_id/character_id identify the join;
    - source_authority pins the original installed primary reward list;
    - mapping_authority declares the explicit profile-to-list-index mapping;
    - parameter_authority declares the meaning of result_parameter;
    - challenge_id/secondary_id match the frozen native publication profile;
    - primary_reward_count/index qualify the actual installed list entry;
    - display_rank is already evaluated (0 unranked, otherwise1..32767);
    - name is the authenticated nullable display name, never an eligibility key;
    - terminal_state/terminal_at_ms come from durable participant/event outcome.

    No claim receipt is required merely to display an earned outcome: capacity
    may leave its separately persisted reward entitlement pending. This function
    does not grant, acknowledge, reserve or mutate that entitlement.
    """
    if type(delivery) is not dict or type(view) is not dict:
        raise ValueError("Missing environmental result joined view")
    if delivery.get("kind") not in ("completed", "expired"):
        return None
    native = view.get("native_result")
    publication = view.get("native_publication")
    if native is None or publication is None:
        return None
    if type(native) is not dict or type(publication) is not dict:
        raise ValueError("Malformed environmental result profile")
    _integer(account_id, "account", 1)
    _integer(character_id, "character", 1)
    instance_id = _integer(view.get("instance_id"), "instance", 1)
    version = _integer(view.get("version"), "version", 1, 2**31 - 1)
    profile_key = view.get("profile_key")
    if type(profile_key) is not str or not profile_key:
        raise ValueError("Missing environmental result profile identity")
    for key, expected in (
        ("instance_id", instance_id),
        ("account_id", account_id),
        ("character_id", character_id),
    ):
        if type(delivery.get(key)) is not int or delivery[key] != expected:
            raise ValueError("Environmental result delivery belongs to another " + key)
        if type(native.get(key)) is not int or native[key] != expected:
            raise ValueError("Environmental result profile belongs to another " + key)
    if (
        native.get("profile_key") != profile_key
        or type(native.get("version")) is not int
        or native["version"] != version
    ):
        raise ValueError("Environmental result profile differs from its frozen event")
    key = delivery.get("delivery_key")
    if type(key) is not str or not key or len(key) > 200:
        raise ValueError("Invalid environmental result delivery key")
    revision = _integer(delivery.get("revision"), "delivery revision", 1)
    for field in ("source_authority", "mapping_authority", "parameter_authority"):
        _authority(native.get(field), field)
    if native.get("terminal_state") != delivery["kind"]:
        raise ValueError(
            "Environmental result differs from its durable terminal outcome"
        )
    _integer(native.get("terminal_at_ms"), "terminal time")
    challenge = native.get("challenge_id")
    secondary = native.get("secondary_id")
    if (
        type(challenge) is not int
        or challenge != view.get("native_scenario_id")
        or challenge != publication.get("challenge_id")
        or type(secondary) is not int
        or secondary != publication.get("secondary_id")
    ):
        raise ValueError("Environmental result differs from its installed challenge")
    count = _integer(
        native.get("primary_reward_count"), "primary reward count", 1, 2**31 - 1
    )
    index = _integer(
        native.get("primary_reward_index"), "primary reward index", 0, count - 1
    )
    # cio casts rank+1 back to short.32767 in the raw rank-minus-one slot
    # would wrap to a negative displayed rank, so cap the *displayed* rank.
    rank = _integer(native.get("display_rank"), "display rank", 0, 32767)
    if "name" not in native:
        raise ValueError("Missing authenticated environmental result name")
    packet = result_packet(
        challenge_id=challenge,
        secondary_id=secondary,
        name=native["name"],
        result_parameter=native.get("result_parameter"),
        rank_minus_one=rank - 1,
        result_value=index,
    )
    return dict(
        delivery_key=key,
        instance_id=instance_id,
        revision=revision,
        kind="native_result",
        packets=(packet,),
    )
