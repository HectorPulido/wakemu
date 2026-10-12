"""Original-client custom task detail display, separate from journal state.

Message 12963 is a passive native message box. Its optional callback opens a
private conversation, so it must never be used for task actions or reward claims.
"""


def task_detail(message):
    """Return a raw-text native popup with no callback or localization lookup.

    The original decoder uses an unsigned byte for each UTF-8 string length.
    Reject oversize text rather than silently losing objective/reward details.
    This packet does not register a mission or modify the native journal.
    """
    if not isinstance(message, str) or not message or "\x00" in message:
        raise ValueError("Custom task detail must be nonempty text without NUL")
    encoded = message.encode("utf-8")
    if len(encoded) > 255:
        raise ValueError("Custom task detail exceeds 255 UTF-8 bytes")
    # Empty callback recipient; inverted booleans disable callback and i18n.
    return 12963, b"\x00" + bytes((len(encoded),)) + encoded + b"\x01\x01"
