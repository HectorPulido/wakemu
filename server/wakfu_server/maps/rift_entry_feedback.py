"""Bounded player-facing explanations for refused atomic Rift admissions."""


class RiftEntryError(ValueError):
    """Keep diagnostic details separate from trusted admission feedback fields."""

    def __init__(self, reason, diagnostic, *, member=None, required_level=None):
        super().__init__(diagnostic)
        self.reason = reason
        self.member_name = None
        if member is not None:
            name = member.get("name") or f"personaje {member['id']}"
            self.member_name = "".join(c for c in str(name) if c.isprintable())[:64]
        self.required_level = required_level


def failure_message(error):
    """Return only known domain messages; never echo unknown exception text."""
    if type(error) is not RiftEntryError:
        return None
    prefix = "No se puede entrar en la brecha: "
    if error.reason == "leader":
        return prefix + (
            "solo el líder del grupo puede iniciar la entrada. "
            "Pídele que use el portal con todos los miembros cerca."
        )
    if error.reason == "party_changed":
        return prefix + (
            "el grupo cambió mientras se preparaba la entrada. "
            "Revisa sus miembros y vuelve a usar el portal con el líder."
        )
    if not error.member_name:
        return None
    if error.reason == "session":
        return prefix + (
            f"{error.member_name} no tiene una sesión activa con ese personaje seleccionado. "
            "Pídele que seleccione su personaje y reúna su compañía junto al portal. "
            "No se ha realizado esta entrada."
        )
    if error.reason == "proximity":
        return prefix + (
            f"{error.member_name} está demasiado lejos del portal. "
            "Acerca a todos los miembros al mismo portal y vuelve a intentarlo. "
            "No se ha realizado esta entrada."
        )
    if error.reason == "location":
        return prefix + (
            f"{error.member_name} está en otro mapa o estancia. "
            "Reúne a todo el grupo junto al mismo portal y vuelve a intentarlo. "
            "No se ha realizado esta entrada."
        )
    if error.reason == "level" and type(error.required_level) is int:
        return prefix + (
            f"{error.member_name} no tiene el nivel mínimo {error.required_level}. "
            "Revisa el nivel de todos los miembros antes de entrar. "
            "No se ha realizado esta entrada."
        )
    return None
