"""Preserve externally supplied combat RNG state on rejected previews."""
from functools import wraps


def rollback_external_rng(operation):
    @wraps(operation)
    def transaction(*args, **kwargs):
        rng = kwargs.get("rng")
        if rng is None:
            return operation(*args, **kwargs)
        if not callable(getattr(rng, "getstate", None)) or not callable(
            getattr(rng, "setstate", None)
        ):
            raise ValueError("External combat RNG requires reversible state")
        before = rng.getstate()
        try:
            return operation(*args, **kwargs)
        except BaseException:
            rng.setstate(before)
            raise

    return transaction
