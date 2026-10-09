"""Server-owned character creation appearance defaults without persistence."""
from protocol_codec import APPEARANCE_FIELDS


def fresh_character_appearance(sex, *, face=0, cloth=0):
    """Mirror Store.create_character's no-appearance, white RGB constructor path."""
    if (
        type(sex) is not int
        or sex not in (0, 1)
        or type(face) is not int
        or face not in range(32)
        or type(cloth) is not int
        or cloth not in range(32)
    ):
        raise ValueError("Invalid fresh character appearance")
    appearance = dict(zip(APPEARANCE_FIELDS[:3], (-1, -1, -1)))
    appearance.update(sex=sex, faceIndex=face, clothIndex=cloth)
    return appearance
