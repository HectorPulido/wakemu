"""Explicit current local-account gift authority for task-list composition.

The current items.gifts.empty_message contract publishes zero local gifts and
capReached=false. No genuine gift database/claim engine exists in this server.
Replace this provider when that authority gains real gifts; never import captured
or official-account gifts and never interpret provider errors as an empty list.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class GiftSnapshot:
    packages: tuple
    cap_reached: bool


def current_local_gifts():
    """Match the existing authoritative local-account empty13369 policy."""
    return GiftSnapshot(packages=(), cap_reached=False)
