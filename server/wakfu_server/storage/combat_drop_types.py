"""Canonical immutable combat loot records shared by both public import paths."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class DropDecision:
    defeated_actor_id: int
    monster_reference: int
    drop_row_index: int
    attempt_index: int
    item_reference: int
    success: bool
    quantity: int | None
    base_probability: Decimal
    raw_probability: Decimal
    effective_probability: Decimal
    draw_numerator: int
    quantity_draw_numerator: int | None
    quantity_min: int
    quantity_max: int
    roll_count: int
    native_roll_max: int
    native_min_prospection: int


@dataclass(frozen=True)
class AwardBatch:
    fight_id: int
    character_id: int
    policy_version: int
    snapshot: dict
    snapshot_sha256: str
    decisions: tuple[DropDecision, ...]
    replayed: bool
