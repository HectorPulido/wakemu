"""Construct a healthy owned tank aptitude build before ordinary actor creation."""
import hashlib
import inspect


def native_tank_fixture(validator, *, feca=False):
    from wakfu_server.aptitudes import BONUSES, BONUS_CATEGORY, budgets, validate
    from wakfu_server.equipment_stats import effective_character
    from wakfu_server.progression import level_xp
    from wakfu_server.wire import proto_field

    allocation = budgets(200)[BONUS_CATEGORY[1]]
    maximum = BONUSES[1]["maximum"]
    if maximum:
        allocation = min(allocation, maximum)
    sheet = proto_field(24, 200)
    aptitudes = sheet + proto_field(34, proto_field(8, 1) + proto_field(16, allocation))
    facts = dict(level=200, aptitude_bonus=1, points=allocation, feca=feca)

    def healthy_owned_character(raw):
        raw = dict(raw)
        raw["builds"] = {
            0: dict(sheet=sheet.hex(), aptitudes=aptitudes.hex(), equipment="")
        }
        validate(raw, aptitudes)
        projection = effective_character(raw)
        # A fresh healthy owner enters the fight at its actual native maximum.
        # This is before Actor construction, never an in-fight heal or resource grant.
        projection = effective_character(dict(raw, hp=projection["max_hp"]))
        facts.update(max_hp=projection["max_hp"], hp=projection["hp"])
        assert projection["hp"] == projection["max_hp"]
        return projection

    original = inspect.getsource(validator.fixture)
    changes = {
        'character_level = buff_recipe["character_level"] if buff_recipe else 1': 'character_level = buff_recipe["character_level"] if buff_recipe else 200',
        "character = effective_character(": "character = _healthy_owned_character(",
        "            level=character_level,\n": "            level=character_level,\n            xp=_native_xp(character_level),\n",
    }
    if feca:
        changes.update(
            {
                'character_breed = buff_recipe["character_breed"] if buff_recipe else 15': 'character_breed = buff_recipe["character_breed"] if buff_recipe else 1',
                'deck = encode_deck([buff_recipe["spell_id"]]) if buff_recipe else encode_deck()': 'deck = encode_deck([buff_recipe["spell_id"]]) if buff_recipe else encode_deck([6972])',
            }
        )
    modified = original
    for before, after in changes.items():
        assert modified.count(before) == 1, ("Ordinary fixture source drift", before)
        modified = modified.replace(before, after)
    namespace = dict(validator.fixture.__globals__)
    namespace.update(
        _healthy_owned_character=healthy_owned_character, _native_xp=level_xp
    )
    exec(compile(modified, "<native-owned-tank-fixture>", "exec"), namespace)
    facts.update(
        source_sha256=hashlib.sha256(modified.encode()).hexdigest(),
        base_fixture_sha256=hashlib.sha256(original.encode()).hexdigest(),
        scope="Fresh owned fixture before Actor construction; no persistent-player heal",
    )
    return namespace["fixture"], facts
