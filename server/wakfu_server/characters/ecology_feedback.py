"""Explain committed ecosystem changes using the exact receipt evidence."""
import struct


def information(text):
    """Native NE/SystemNotification subtype 4, delivered to GAME_INFORMATION."""
    if not isinstance(text, str):
        raise ValueError("Information requires text")
    encoded = text.encode("utf-8")
    if len(encoded) > 32767:
        raise ValueError("Information text exceeds native signed-short length")
    return 349, struct.pack(">hh", 4, len(encoded)) + encoded


def _percent(number):
    return f"{abs(number) / 100:.2f}".replace(".", ",")


def _affinity(number):
    return (
        "Neutral"
        if number == 0
        else f"{_percent(number)}% {'Wakfu' if number > 0 else 'Stasis'}"
    )


def describe(receipt):
    evidence = receipt["evidence"]
    before, after = receipt["before_value"], receipt["after_value"]
    difference = after - before
    distance_before, distance_after = (
        evidence["distance_before"],
        evidence["distance_after"],
    )
    effect = (
        "mejora el equilibrio"
        if distance_after < distance_before
        else "empeora el equilibrio"
        if distance_after > distance_before
        else "mantiene el equilibrio"
        if distance_before == 0
        else "no reduce el desequilibrio"
    )
    result = (
        f"{_percent(difference)} puntos hacia {'Wakfu' if difference > 0 else 'Stasis'}"
        if difference
        else "sin cambio de afinidad"
    )
    return (
        f"Ecosistema: población {evidence['before_population']} → {evidence['after_population']}; "
        f"rango de equilibrio {evidence['minimum']}–{evidence['maximum']}. "
        f"Tu acción {effect}: {result}. "
        f"Afinidad: {_affinity(before)} → {_affinity(after)}."
    )
