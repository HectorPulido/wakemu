"""Compile a local family encounter without requiring an archived guide base."""
import copy

ORDINARY_TYPES = frozenset(
    {"DUNGEON_2_ROOMS", "DUNGEON_3_ROOMS", "DUNGEON_4_ROOMS", "DUNGEON_3_PLAYERS"}
)


def base(record, route, rooms):
    """Return builder input; native identity and encounter bounds remain strict."""
    from wakfu_server import dungeon_instances
    from wakfu_server.maps.dungeon_runtime_config import canonical_hash

    native = record.get("native") or {}
    if native.get("type") not in ORDINARY_TYPES:
        raise ValueError("Family generation requires an ordinary dungeon")
    if record.get("name_es", "").lower().startswith("neo"):
        raise ValueError("Neo variants are outside the classic family policy")
    if route.get("definition_id") != native.get("id"):
        raise ValueError("Family base route contradicts native dungeon identity")
    dungeon_instances._load_routes([route])
    pool = {m["ref_id"]: m for m in record["native_species_pool"]}
    orders = [r["order"] for r in rooms]
    if not orders or orders != list(range(1, len(rooms) + 1)):
        raise ValueError("Family encounter stages must be contiguous")
    bosses = set()
    for room in rooms:
        if not room["monsters"]:
            raise ValueError("Family stage has no encounter")
        for monster in room["monsters"]:
            ref = pool.get(monster.get("ref_id"))
            if ref is None:
                raise ValueError("Family encounter species is not in its native pool")
            if type(monster.get("count")) is not int or monster["count"] <= 0:
                raise ValueError("Family encounter quantity must be positive")
            if (monster.get("native_min_level"), monster.get("native_max_level")) != (
                ref["min_level"],
                ref["max_level"],
            ):
                raise ValueError("Family encounter contradicts native level bounds")
            role = monster.get("role")
            if role not in ("monster", "boss"):
                raise ValueError("Family encounter role is not explicit")
            if role == "boss":
                if room["order"] != len(rooms) or monster["count"] != 1:
                    raise ValueError("Family bosses occur once in the final stage only")
                if monster["ref_id"] in bosses:
                    raise ValueError("Family boss is duplicated")
                bosses.add(monster["ref_id"])
    if not bosses:
        raise ValueError("Family dungeon requires an identified final boss")
    slug = route["key"]
    provenance = "User-authorized local family composition; native dungeon species and levels; identified bosses only in the final encounter"
    plan = dict(
        slug=slug,
        source_url="",
        source_sha256=canonical_hash(
            dict(native=native, species=record["native_species_pool"])
        ),
        document_sha256=canonical_hash(rooms),
        definition_id=route["definition_id"],
        template_id=route["template_id"],
        asset_map_id=route["start_map_id"],
        rooms=[
            dict(
                order=r["order"], monsters=copy.deepcopy(r["monsters"]), diagnostics=[]
            )
            for r in rooms
        ],
        diagnostics=[],
        roster_ready=True,
        policy_mode="user_authorized_native_family_encounters",
        official=False,
        reviewed_official=False,
        boss_references=sorted(bosses),
        species_pool_provenance="Installed native dungeon species pool",
        local_policy=provenance,
    )
    return dict(
        route=copy.deepcopy(route), compiled_plan=plan, version=0, provenance=provenance
    )
