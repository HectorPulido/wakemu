"""Configurable bounds for HTTP workers and active native searches."""
import os


def capacities(environ=None):
    environ = os.environ if environ is None else environ
    values = []
    for name, default, maximum in (
        ("WAKFU_AI_MAX_DECISIONS", 16, 64),
        ("WAKFU_AI_MAX_CONNECTIONS", 64, 128),
    ):
        raw = environ.get(name, str(default))
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be an integer") from None
        if not 1 <= value <= maximum:
            raise ValueError(f"{name} must be between 1 and {maximum}")
        values.append(value)
    if values[1] < values[0]:
        raise ValueError("AI connection capacity must cover decision capacity")
    return tuple(values)
