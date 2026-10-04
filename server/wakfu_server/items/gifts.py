"""Local accounts have no captured official gifts or claimable gift IDs."""


def empty_message(opcode):
    if opcode == 12722:
        return b"\x00"  # cwi: false gift-status flag
    if opcode == 13369:
        return b"\x00\x00\x00"  # cwj: zero uD entries, capReached=false
    raise ValueError("Unsupported gift message")
