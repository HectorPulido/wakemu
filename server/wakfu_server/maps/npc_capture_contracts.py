"""Exact captured NPC bindings; publication authorization is local policy.

A native capture proves the actor/action/root and observed position. It does not
prove universal story visibility. No generic hostile identity is admitted.
"""

FIELDS = (
    "actor_id",
    "reference_id",
    "map_id",
    "x",
    "y",
    "z",
    "direction",
    "dialogue_root",
)


def authorized_identity(row):
    contract = row.get("native_capture_contract")
    identity = row["actor_id"]
    if (
        not isinstance(contract, dict)
        or type(identity) is not int
        or not -(2**53) < identity < 0
        or row.get("native_capture_id") != identity
        or row.get("native_publication_authorized") is not True
        or contract.get("publication_authorized") is not True
        or row["instance_id"] != 0
        or any(row.get(key) != contract.get(key) for key in FIELDS)
        or row.get("action_ids") != contract.get("action_ids")
    ):
        return False
    digest = contract.get("source_sha256", "")
    return (
        isinstance(digest, str)
        and len(digest) == 64
        and all(char in "0123456789abcdef" for char in digest)
    )
