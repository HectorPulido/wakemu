"""Typed public ecology failures and bounded private server diagnostics."""

from wakfu_server.request_diagnostics import exception_frames, redact


PUBLIC_FAILURES = {
    "no_monster_habitat": (
        "No native monster habitat for administrative population",
        "Esta zona no tiene un hábitat nativo de monstruos; !genesis no puede crear población aquí.",
    ),
}


class EcologyAdminFailure(ValueError):
    """Expose only an explicitly approved explanation to the player."""

    def __init__(self, code):
        if code not in PUBLIC_FAILURES:
            raise ValueError("Unknown administrative ecology failure code")
        self.code = code
        super().__init__(PUBLIC_FAILURES[code][0])


class EcologyPreparationFailure(ValueError):
    """Retain the isolated worker's diagnostics without making them public."""

    def __init__(self, details):
        self.details = details
        super().__init__("Administrative native habitat preparation failed")


def public_failure(code):
    if not isinstance(code, str):
        return None
    row = PUBLIC_FAILURES.get(code)
    return None if row is None else row[1]


def failure_details(error):
    if isinstance(error, EcologyPreparationFailure):
        return dict(error.details)
    return dict(
        error_type=type(error).__name__,
        error_code=error.code if isinstance(error, EcologyAdminFailure) else None,
        reason=redact(str(error)),
        traceback=exception_frames(error),
    )
