"""Native damage/healing family identities without arithmetic or catalogs.

These declarations describe existing routes. Native parameter, flag, targeting
and execution contexts still decide eligibility and supported variants.
"""

DAMAGE_FAMILIES = (1, 2, 3, 4, 5, 917, 1083)

# eXv24 inherits healing consumption but derives value without elemental mastery.
HEAL_ELEMENTS = {24: None, 25: 1, 251: 5, 253: 3, 258: 4, 259: 2, 1084: 6}
