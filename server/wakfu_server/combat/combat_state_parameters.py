"""Native eWu class304 applicator parameter subset.

C(Qe) narrows reference and level to signed short.
Zero is a valid native state level (eWu.eq -> signed short; fyW.cu
retains it); negative dynamic modes remain explicitly unsupported.
Third parameter is an independent state-application chance, not the effect's generic probability.
The catalogue's -1 sentinel returns100 in fNa without state resistance math.
Other probabilities and dynamic spell/state-level modes remain explicit.
"""


def interpret_state_parameters(parameters):
    if len(parameters) != 3 or any(type(v) is not int for v in parameters):
        raise ValueError("Unsupported native state applicator parameter mode")
    reference, level, chance = parameters
    reference = ((reference + 32768) % 65536) - 32768
    level = ((level + 32768) % 65536) - 32768
    if reference <= 0 or level < 0:
        raise ValueError("Unsupported native state reference/level")
    if chance != -1:
        raise ValueError(
            "State application chance requires native resistance and random context"
        )
    return dict(reference=reference, level=level, application_chance=100)
