"""Actual fyG PL element operand used by eYW.fQG, including native null."""
from dataclasses import dataclass
from functools import lru_cache
from wakfu_server import native_catalog as protocol_catalog
from wakfu_server.paths import DATA_ROOT
from .combat_life_steal import native_spell_elements

SOURCE = "eYW.fQG.fyG.gtZ.fyF.gtQ.eVg.fa.fLC.aKg.v1"


@dataclass(frozen=True)
class NativeSpellElementPC:
    native_element: int
    element_name: str
    characteristic_id: int | None


@lru_cache(maxsize=1)
def native_spell_element_damage_pcs():
    return protocol_catalog.load(DATA_ROOT / "native-spell-element-damage-pcs.json")


def spell_element_pc(container, identity):
    if (
        not isinstance(container, dict)
        or container.get("container_present") is not True
        or container.get("container_type") != 11
        or container.get("container_is_spell") is not True
        or type(identity) is not int
        or not 0 < identity < (1 << 63)
        or container.get("container_id") != identity
    ):
        raise ValueError("Missing actual native fyG PL identity")
    spell = native_spell_elements().get(str(identity >> 16))
    if not isinstance(spell, dict) or type(spell.get("native_element")) is not int:
        raise ValueError("Missing actual native fyF element metadata")
    catalog = native_spell_element_damage_pcs()
    element = spell["native_element"]
    row = catalog.get("elements", {}).get(str(element))
    if (
        catalog.get("source") != SOURCE
        or not isinstance(row, dict)
        or row.get("native_element") != element
        or row.get("element_name") != spell.get("element_name")
        or "damage_stat" not in row
    ):
        raise ValueError("Missing native eVg.fLC element PC authority")
    stat = row["damage_stat"]
    if stat is None:
        if catalog.get("null_pc_present") is not False:
            raise ValueError("Missing native source PV null-PC absence authority")
    elif type(stat) is not int or not -128 <= stat <= 127:
        raise ValueError("Invalid native eVg.fLC PC identity")
    return NativeSpellElementPC(element, row["element_name"], stat)
