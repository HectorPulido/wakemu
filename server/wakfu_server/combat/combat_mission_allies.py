"""Typed admission for quest-owned, AI-controlled ordinary NPC allies.

Quest producers authorize the durable mission/instance before calling admit.
The shared combat constructor owns native stats, spell books, AI and teams;
this adapter declares only the immutable scene role and excludes ally rewards.
"""

from dataclasses import dataclass

POLICY = "wakemu.astrub.cat-story.native-ally.v1"
DECLARATIONS = {
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
