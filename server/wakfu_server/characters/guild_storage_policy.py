"""Native guild storage authority and an explicit opt-in Wakemu policy.

The native client defines compartment dimensions, rank rights and learned
compartment gates. Every compartment retains its durable native unlock state.
This module never changes live settings.
"""
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

MODEL = "native_guild_storage_v1"
CATALOG_SHA256 = "e3ddde8165fd6c82c0d2fa19ecac2485fb4707d35f56b22a9963684423d517a4"


@lru_cache(maxsize=1)
def catalog():
    raw = Path(__file__).with_name("native_guild_storage.json").read_bytes()
    if sha256(raw).hexdigest() != CATALOG_SHA256:
        raise ValueError("Conflicting native guild storage authority")
    data = json.loads(raw)
    if data.get("schema_version") != 1 or len(data.get("chests", ())) != 9:
        raise ValueError("Incomplete native guild storage authority")
    return data


def storage_policy(base, *, enabled=False):
    """Compose qualified storage with the supplied management/identity policy."""
    if type(enabled) is not bool or not isinstance(base, dict):
        raise ValueError("Invalid guild storage policy")
    policy = deepcopy(base)
    if enabled and (
        policy.get("enabled") is not True
        or policy.get("native_sync_enabled") is not True
        or policy.get("primary_identity_only") is not False
    ):
        raise ValueError("Guild storage requires enabled general guild membership")
    policy["chest"] = {
        "enabled": enabled,
        "policy_origin": "native_storage_v1_learned_compartments",
        "compartments": {
            str(index): {
                "capacity": 40,
                "name": f"Guild Chest {index + 1}",
                "requires_unlock": True,
                "permission_model": MODEL,
                "compartment_id": index,
            }
            for index in range(4)
        },
        "access_points": deepcopy(catalog()["chests"]),
    }
    economy = policy.setdefault("economy", {})
    economy["treasury_enabled"] = enabled
    economy["permission_model"] = MODEL
    # Point rewards, caps and bonus unlocks are independent authorities. They
    # are preserved verbatim, never enabled as a side effect of shared custody.
    return policy


def chest_permission(definition, permissions, action):
    """bQC.emH: REMOVE_CHEST_ITEM OR this fik's MANAGE_GUILD_CHEST_n.

    Viewing, adding and rearranging do not transfer shared property to a
    member. Their original client path has no removal-authorization check.
    Membership and compartment availability are checked by the caller.
    """
    if (
        definition.get("permission_model") != MODEL
        or type(permissions) is not int
        or not 0 <= permissions < 2**63
    ):
        raise ValueError("Invalid native guild storage permission authority")
    compartment = definition.get("compartment_id")
    if type(compartment) is not int or not 0 <= compartment <= 3:
        raise ValueError("Invalid native guild compartment identity")
    if action in ("view", "deposit", "move"):
        return True
    if action == "withdraw":
        return bool(permissions & ((1 << 5) | (1 << (11 + compartment))))
    raise ValueError("Unknown native guild storage permission action")


def treasury_permission(permissions, action):
    """bQE.emM requires REMOVE_CHEST_MONEY; depositing requires membership."""
    if type(permissions) is not int or not 0 <= permissions < 2**63:
        raise ValueError("Invalid native guild treasury permission authority")
    if action == "treasury_deposit":
        return True
    if action == "treasury_withdraw":
        return bool(permissions & (1 << 8))
    raise ValueError("Unknown native guild treasury permission action")
