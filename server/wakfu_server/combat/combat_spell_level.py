"""eLo/fzj owned spell lookup, independent of spell deck membership."""
from dataclasses import dataclass


@dataclass(frozen=True)
class NativeSpellBook:
    # None denotes proven native dok()==null, never missing authority.
    levels: dict | None
    player_character: bool
    progression_levels: dict | None = None
    deck_cap: int | None = None

    def level(self, reference):
        if type(self.player_character) is not bool:
            raise ValueError("Unknown native PLAYER_CHARACTER membership")
        if self.levels is None:
            return 0
        for population in (self.levels, self.progression_levels):
            if population is not None and (
                not isinstance(population, dict)
                or any(
                    type(k) is not int
                    or not -(1 << 31) <= k < (1 << 31)
                    or type(v) is not int
                    or not -32768 <= v <= 32767
                    for k, v in population.items()
                )
            ):
                raise ValueError("Invalid complete native owned spellbook")
        if reference not in self.levels:
            return 0
        if not self.player_character:
            return self.levels[reference]
        if self.progression_levels is None or reference not in self.progression_levels:
            return -1
        if self.deck_cap is not None and type(self.deck_cap) is not int:
            raise ValueError("Invalid native spell deck cap")
        level = self.progression_levels[reference]
        # fzf.gvc is tL < 0; zero is an actual execution cap.
        return (
            level
            if self.deck_cap is None or self.deck_cap < 0
            else min(level, self.deck_cap)
        )


def decoded_spell_levels(records, definitions):
    """fyR.b(yC) -> fyG.e(yy) -> cr(short): clamp to native fyF.Fq."""
    from .combat_published_catalogs import static_row_scalar

    levels = {}
    for _, reference, level in records:
        maximum = static_row_scalar(definitions, str(reference), "maximum_level")
        if type(maximum) is not int or not 0 <= maximum <= 32767:
            raise ValueError("Missing native owned spell maximum level")
        if reference in levels:
            raise ValueError("Duplicate owned native spell reference")
        levels[reference] = min(level, maximum)
    return levels
