"""Project only the installed native ADMIN_CHAT permission from account roles."""
import struct


ADMIN_CHAT_WORD = 3
ADMIN_CHAT_MASK = 1 << 14


def project_account_information(body, *, is_admin):
    """Preserve the native oJ section, changing only permission ordinal110."""
    if not isinstance(body, bytes) or type(is_admin) is not bool or len(body) < 2:
        raise ValueError("Invalid native account information")
    count = struct.unpack_from(">H", body)[0]
    end = 2 + count * 4
    if end > len(body):
        raise ValueError("Truncated native account rights")
    words = list(struct.unpack_from(f">{count}I", body, 2))
    if is_admin:
        words.extend([0] * max(0, ADMIN_CHAT_WORD + 1 - count))
        words[ADMIN_CHAT_WORD] |= ADMIN_CHAT_MASK
    elif count > ADMIN_CHAT_WORD:
        words[ADMIN_CHAT_WORD] &= ~ADMIN_CHAT_MASK
    return (
        struct.pack(">H", len(words))
        + struct.pack(f">{len(words)}I", *words)
        + body[end:]
    )
