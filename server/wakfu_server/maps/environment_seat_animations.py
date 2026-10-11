"""Original ordinary class model ANM sitting-animation qualification.

All 9,216 original bhe class/sex/cloth selections resolve to these 44 models.
Original Dz/Fl.by lookup proves all three sitting keys for every model. This
producer applies to ordinary world characters, never transformed actor models.
"""
from wakfu_server.combat_character_copy_models import native_class_copy_model
from wakfu_server.wire import ENTITY_DEFAULTS
from protocol_codec import APPEARANCE_FIELDS

_CERTIFIED_MODELS = frozenset(
    [
        10,
        11,
        20,
        21,
        30,
        31,
        32,
        33,
        40,
        41,
        42,
        43,
        50,
        51,
        52,
        53,
        60,
        61,
        70,
        71,
        80,
        81,
        90,
        91,
        100,
        101,
        110,
        111,
        120,
        121,
        130,
        131,
        140,
        141,
        150,
        151,
        160,
        161,
        162,
        163,
        180,
        181,
        190,
        191,
    ]
)


def supported(character, *, ordinary_actor=False):
    if type(ordinary_actor) is not bool or not ordinary_actor:
        return False
    appearance = character.get("appearance")
    if (
        ENTITY_DEFAULTS.get("EQUIPMENT_APPEARANCE") != b"\x00"
        or not isinstance(appearance, dict)
        or any(key not in APPEARANCE_FIELDS for key in appearance)
    ):
        return False
    sex = appearance.get("sex", 0)
    cloth = appearance.get("clothIndex", 0)
    if type(sex) is not int or type(cloth) is not int:
        return False
    byte = lambda value: (value + 128) % 256 - 128
    try:
        model = native_class_copy_model(character.get("breed"), byte(sex), byte(cloth))
    except ValueError:
        return False
    return model in _CERTIFIED_MODELS
