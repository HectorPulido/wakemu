"""Typed admission for quest-owned, AI-controlled ordinary NPC allies.

Quest producers authorize the durable mission/instance before calling admit.
The shared combat constructor owns native stats, spell books, AI and teams;
this adapter declares only the immutable scene role and excludes ally rewards.
"""

from dataclasses import dataclass

POLICY = "wakemu.astrub.cat-story.native-ally.v1"
VOYAGE_POLICY = "wakemu.zinit.voyage.native-ally.v1"
BOVIS_POLICY = "wakemu.bovis-lair.native-ally.v1"
DECLARATIONS = {
    BOVIS_POLICY: {
        "mission": 2711,
        "map_id": 1002,
        "rooms": {3: (3840, 3841), 4: (3845,)},
        "helpers": (("mimi", 3854, 25, "player", "self"),),
        "facts": (
            "Original2045 room3/16175 and room4/16207 declare Mimi in combat",
            "Native3854 level25, original5509/5511 and4206 initial state retained",
            "Native3842 has no spellbook and is not fabricated as an ordinary enemy",
            "Real owned TeamMissile and Bovis victories remain separate story outcomes",
        ),
    },
    VOYAGE_POLICY: {
        "mission": 2684,
        "map_id": 980,
        "rooms": {
            1: (3771, 3771, 3771),
            2: (3783, 3783, 3783, 3784, 3784),
            3: (3769, 3769, 3769, 3770, 3770, 3770),
        },
        "helpers": (("sailor", 3781, 15, "player", "self"),),
        "facts": (
            "native3781:Micho Pera level15/HP50; sprite177903781; spell5147",
            "native family779 voyage birds/pirates/tornadoes preserve original grades/spells",
            "Reviewed relocation of obsolete2015/2018/2016 map290/303/304 onto current980 ship",
            "Three/five/six formation counts corroborated by journey guide; composition is reviewed reconstruction",
        ),
    },
    POLICY: {
        "mission": 5568,
        "map_id": 312,
        "rooms": {
            1: (2616, 2616, 2616),
            2: (2616, 2616, 2617),
            3: (1816, 2616, 2617),
        },
        "helpers": (("tristepin", 4691, 6, "player", "self"),),
        "facts": (
            "native4691:level6/HP200/AP8/MP4/WP4/INIT6",
            "native4691:6402/6403/6404; sprite192404687",
            "scenario1340:Pipoun battle ally;4687 is the noncombat scene actor",
            "quest5568:three reconstructed cave encounter rosters",
        ),
    },
}


@dataclass(frozen=True)
class MissionAlliesAdmission:
    policy: str
    principal_id: int
    account_id: int
    map_id: int
    instance_id: int
    room: int
    members: tuple

    def record(self):
        return dict(
            policy=self.policy,
            principal_id=self.principal_id,
            account_id=self.account_id,
            map_id=self.map_id,
            instance_id=self.instance_id,
            room=self.room,
            members=[list(row) for row in self.members],
        )


def declaration(policy):
    return DECLARATIONS.get(policy)


def admit(character, members, *, policy=POLICY, room):
    """Freeze a producer-authorized quest encounter; never accept client data."""
    contract = declaration(policy)
    if contract is None:
        raise ValueError("Unknown mission ally declaration")
    refs = tuple(sorted(member["ref"] for member in members))
    if (
        type(room) is not int
        or contract["rooms"].get(room) != refs
        or character.get("map_id") != contract["map_id"]
        or type(character.get("instance_id")) is not int
        or character["instance_id"] <= 0
        or type(character.get("id")) is not int
        or character["id"] <= 0
        or type(character.get("account_id")) is not int
        or character["account_id"] <= 0
        or any(type(m.get("id")) is not int or m["id"] >= 0 for m in members)
        or len({m["id"] for m in members}) != len(members)
    ):
        raise ValueError("Mission ally admission differs from its owned room")
    return MissionAlliesAdmission(
        policy,
        character["id"],
        character["account_id"],
        character["map_id"],
        character["instance_id"],
        room,
        tuple((m["id"], m["ref"], m["x"], m["y"], m["z"]) for m in members),
    )


def validate(admission, character, members):
    if type(admission) is not MissionAlliesAdmission:
        raise ValueError("Mission allies need a server-owned typed admission")
    expected = admit(character, members, policy=admission.policy, room=admission.room)
    if admission != expected:
        raise ValueError(
            "Mission ally admission escaped its original character or roster"
        )
    return declaration(admission.policy)


def validate_manifest(source):
    """Recheck the plain frozen declaration after persistence or preview cloning."""
    declaration_row = declaration(source.get("policy"))
    if declaration_row is None:
        raise ValueError("Unknown mission ally manifest")
    record = source.get("mission_admission")
    if not isinstance(record, dict):
        raise ValueError("Mission ally manifest lost its admission")
    character = {key: source[key] for key in ("map_id", "instance_id", "account_id")}
    character["id"] = source["principal_id"]
    members = [
        dict(
            id=row["id"],
            ref=row["reference"],
            **dict(zip(("x", "y", "z"), row["position"]))
        )
        for row in source["originals"]
    ]
    expected = admit(
        character, members, policy=source["policy"], room=record.get("room")
    )
    if expected.record() != record:
        raise ValueError("Mission ally manifest differs from its frozen admission")
    helpers = source.get("helpers")
    if (
        not isinstance(helpers, list)
        or len(helpers) != len(declaration_row["helpers"])
        or any(
            (
                row.get("role"),
                row.get("reference"),
                row.get("level"),
                row.get("team_role"),
                row.get("controller_role"),
            )
            != declared
            or row.get("reward_eligible") is not False
            for row, declared in zip(helpers, declaration_row["helpers"])
        )
    ):
        raise ValueError("Mission ally manifest changed its native ally declaration")
    return declaration_row
