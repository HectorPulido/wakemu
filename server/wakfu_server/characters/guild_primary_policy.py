"""Explicit Wakemu policy for the native guild identity routes.

Native structural name/blazon/rank definitions are recovered data. Account
ownership, zero additional fees, disabled local censorship and zero projections
for disabled guild economy are deliberate Wakemu choices, not server extracts.
This constructor never reads or writes live settings and defaults to disabled.
"""


def policy(*, enabled=False):
    if type(enabled) is not bool:
        raise ValueError("Invalid guild primary capability flag")
    from wakfu_server.guild_native_validators import catalog

    native = catalog()
    return {
        "enabled": enabled,
        "native_sync_enabled": enabled,
        "primary_identity_only": True,
        "policy_origin": "wakemu_primary_identity_v1",
        "owner_id_semantics": "account",
        "creation_item": 16942,
        "creation_kamas": 0,
        "identity_changes": {
            "name": {"enabled": True, "authority": "leader", "item": 25101, "kamas": 0},
            "blazon": {
                "enabled": True,
                "authority": "leader",
                "item": 25100,
                "kamas": 0,
            },
        },
        "name_normalization": "NFKC_CASEFOLD",
        "name_validation": "native_structure",
        "local_name_censorship": {"enabled": False, "patterns": []},
        "leader_permissions": native["highest_rank_authorizations"],
        "member_permissions": native["lowest_rank_authorizations"],
        "max_members": 200,
        "max_ranks": 15,
        "permissions": {},
        "invitation_seconds": 86400,
        "description_max_bytes": None,
        "message_max_bytes": None,
        "catalog": {},
        "moderation_bonus_learning_factor": 0,
        "weekly_points_limit": 0,
        "earned_points_limit": 0,
        "last_earning_point_week": 0,
        "economy": {
            "treasury_enabled": False,
            "progression_enabled": False,
            "bonuses_enabled": False,
            "permission_bits": {},
            "point_sources": {},
            "weekly_point_cap": None,
            "bonus_catalog": {},
        },
        "chest": {"enabled": False},
    }


MANAGEMENT_OPCODES = (
    13757,
    12937,
    12575,
    15877,
    13744,
    15194,
    14088,
    14815,
    15429,
    15542,
    15627,
    14230,
    15481,
    15511,
    14890,
    14995,
)


def management_policy(*, enabled=False):
    """Native guild management with explicit local text and invitation limits.

    Permission positions come from the installed native enum. Economy and
    chest capabilities remain independent; this constructor enables neither.
    """
    from wakfu_server.guild_native_validators import permission_bits

    result = policy(enabled=enabled)
    bits = permission_bits()
    result.update(
        primary_identity_only=False,
        management_enabled=True,
        policy_origin="wakemu_guild_management_v1",
        native_request_opcodes=list(MANAGEMENT_OPCODES),
        description_max_bytes=4096,
        message_max_bytes=4096,
        permissions={
            action: bits[native]
            for action, native in {
                "invite": "ADD_MEMBER",
                "rank_create": "EDIT_RANK",
                "rank_edit": "EDIT_RANK",
                "rank_remove": "EDIT_RANK",
                "rank_move": "EDIT_RANK",
                "member_rank": "CHANGE_MEMBER_RANK",
                "kick": "REMOVE_MEMBER",
                "description": "CHANGE_GUILD_DESCRIPTION",
                "message": "CHANGE_GUILD_MESSAGE",
            }.items()
        },
    )
    return result
