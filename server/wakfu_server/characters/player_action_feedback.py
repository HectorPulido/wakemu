"""Explain rejected player actions without exposing internal exception text."""
from wakfu_server.equipment_stacks import EquipmentOwnershipError


_ACTIONS = {
    "build_save": "guardar la build",
    "inventory_move": "mover el objeto",
    "exchange": "intercambiar los objetos",
    "hero_selection": "seleccionar el personaje",
    "hero_switch": "cambiar de héroe",
    "transport": "usar este acceso",
    "rift_entry": "entrar en la brecha",
    "harvest": "recolectar este recurso",
    "recycling": "reciclar los objetos",
    "furniture": "modificar el mobiliario",
}


def _retry_message(action, action_text):
    retry = {
        "build_save": "Vuelve a abrir la build y revisa sus selecciones antes de guardar.",
        "inventory_move": "Vuelve a abrir el inventario normal y elige de nuevo el objeto y su destino.",
        "exchange": "Reabre el intercambio y vuelve a seleccionar los objetos antes de confirmar.",
        "hero_selection": "Vuelve a abrir la selección de personajes e inténtalo de nuevo.",
        "hero_switch": "Revisa el grupo de héroes y vuelve a seleccionar el personaje.",
        "transport": "Vuelve a abrir el acceso desde su ubicación actual e inténtalo de nuevo.",
        "rift_entry": "Revisa el grupo y vuelve a abrir el acceso a la brecha.",
        "harvest": "Revisa el recurso y sus requisitos y vuelve a seleccionarlo.",
        "recycling": "Vuelve a abrir el reciclaje y revisa los objetos seleccionados y el espacio de tus bolsas.",
        "furniture": "Vuelve a abrir el modo de edición y selecciona de nuevo el mueble y su ubicación.",
    }.get(action, "Vuelve a abrir la ventana de esta acción e inténtalo de nuevo.")
    return f"No se pudo {action_text}. {retry} Si persiste, informa del error."


def failure_message(action, error):
    """Map bounded domain reasons to a cause and an actionable next step."""
    action_text = _ACTIONS.get(action, "completar esta acción")
    prefix = f"No se puede {action_text}: "
    if type(error).__module__.startswith(("psycopg", "psycopg_pool")):
        return _retry_message(action, action_text)
    if action == "rift_entry":
        from wakfu_server.rift_entry_feedback import (
            failure_message as rift_failure_message,
        )

        message = rift_failure_message(error)
        if message is not None:
            return message
    reason = str(error).casefold()
    if isinstance(error, EquipmentOwnershipError):
        return error.player_message
    if (
        action == "exchange"
        and reason == "native item binding or criterion prohibits exchange"
    ):
        return prefix + (
            "el vínculo o las reglas de este objeto impiden intercambiarlo. "
            "Revisa sus condiciones y retíralo de la oferta para continuar."
        )
    if action in ("exchange", "inventory_move") and any(
        part in reason
        for part in (
            "item is unavailable or foreign",
            "item disappeared before publication",
        )
    ):
        return prefix + (
            "el objeto ya no está disponible en el inventario de ese personaje. "
            "Actualiza el inventario y vuelve a seleccionar un objeto que siga allí."
        )
    if action == "inventory_move" and reason in (
        "partial item uid was not reserved by this session",
        "reserved item uid already consumed by another request",
    ):
        return prefix + (
            "la reserva para dividir esa pila ya no es válida. "
            "Reabre el inventario y vuelve a dividir la pila original."
        )
    if reason == "position owner is busy; retry checkpoint":
        return prefix + (
            "tu posición todavía se está guardando. Espera un momento y vuelve a intentarlo."
        )
    if "party changed during dungeon entry" in reason:
        return prefix + (
            "el grupo cambió mientras se preparaba la entrada. Revisa sus miembros "
            "y que estén cerca del acceso, y vuelve a intentarlo."
        )
    if any(
        part in reason
        for part in (
            "only the selected party leader may enter",
            "only selected party leader may enter",
            "only the current party leader may enter",
        )
    ):
        return prefix + (
            "solo el líder del grupo puede iniciar la entrada. Pídele que use el "
            "acceso o selecciona al líder antes de intentarlo."
        )
    if (
        getattr(error, "feedback_kind", None) == "equipped_item"
        or "desequip" in reason
        or "unequip" in reason
    ):
        next_step = {
            "recycling": "vuelve a seleccionar los objetos que quieres reciclar.",
            "exchange": "vuelve a ofrecerlo en el intercambio.",
        }.get(
            action,
            "muévelo desde el inventario normal de bolsas, fuera del editor de builds.",
        )
        return prefix + (
            "el objeto sigue equipado en una build. Quítalo de todas las builds "
            f"que lo usan y guarda los cambios; después {next_step}"
        )
    if "combat" in reason or "during an occupation" in reason:
        return prefix + (
            "hay un combate o una acción en curso. Termínala antes de volver a intentarlo."
        )
    if "frozen" in reason or "does not share" in reason:
        return prefix + (
            "la composición del grupo está fijada por una mazmorra o brecha activa. "
            "Selecciona un héroe que ya esté en la misma estancia; para cambiar "
            "los integrantes, termina la estancia o sal de ella con todo el grupo."
        )
    if "already pending" in reason or "pending transition" in reason:
        return prefix + (
            "ya hay un cambio de personaje o de mapa pendiente. Espera a que termine "
            "antes de volver a intentarlo."
        )
    if "character-bound" in reason:
        return prefix + (
            "el objeto está ligado a un personaje y no puede pasar a otro héroe. "
            "Úsalo con su propietario."
        )
    if "offered" in reason:
        return prefix + (
            "el objeto está reservado en un intercambio. Retíralo del intercambio "
            "o cancélalo antes de volver a intentarlo."
        )
    if "active owned hero" in reason or "inactive hero" in reason:
        return prefix + (
            "el personaje no forma parte del grupo de héroes activo. "
            "Revisa la composición del grupo y vuelve a abrir su inventario o build."
        )
    if any(
        part in reason
        for part in (
            "capacity",
            "free slot",
            "inventory full",
            "inventory is full",
            "destination full",
            "not enough room",
            "not enough space",
            "no space",
            "nospace",
            "cannot hold recycling products",
        )
    ):
        if action == "build_save" and "build capacity" in reason:
            return prefix + (
                "no tienes una ranura disponible para esa build. "
                "Revisa tus builds disponibles antes de guardar."
            )
        return prefix + (
            "no hay espacio disponible en el inventario de destino. "
            "Deja una casilla libre en una bolsa normal y vuelve a intentarlo."
        )
    if (
        "cannot merge" in reason
        or "cannot be merged" in reason
        or "cannot swap" in reason
    ):
        return prefix + (
            "estos objetos no se pueden apilar o intercambiar entre esas casillas. "
            "Mueve el objeto a una casilla vacía."
        )
    if "cannot be split" in reason:
        return prefix + (
            "esa pila no se puede dividir. Mueve la pila completa a una casilla vacía."
        )
    if action == "build_save":
        if "aptitude" in reason:
            return prefix + (
                "la distribución de características no es válida para esta build. "
                "Revisa los puntos disponibles y vuelve a guardar."
            )
        if "spell" in reason or "deck" in reason:
            return prefix + (
                "la selección de hechizos no es válida para esta build. "
                "Revisa sus hechizos y pasivos y vuelve a guardar."
            )
        if "equipment" in reason or "equip" in reason:
            return prefix + (
                "algún equipable no cumple los requisitos o ya no está disponible. "
                "Revisa el nivel, las condiciones y el inventario del personaje."
            )
    if action in ("transport", "rift_entry") and (
        "criterion" in reason or "requirement" in reason
    ):
        return prefix + (
            "no se han podido validar los requisitos de entrada. "
            "Revisa las condiciones del acceso y las de todos los miembros del grupo."
        )
    if action == "recycling" and any(
        part in reason
        for part in (
            "not recyclable",
            "cannot be recycled",
            "forbids recycling",
        )
    ):
        return prefix + (
            "algún objeto no admite reciclaje en su estado actual. "
            "Retíralo de la selección y revisa sus condiciones antes de continuar."
        )
    if action == "furniture" and "unsupported" in reason:
        return prefix + (
            "esa operación de mobiliario todavía no está disponible. "
            "Cierra el modo de edición y vuelve al inventario."
        )
    if any(
        word in reason
        for word in (
            "session",
            "desynchronized",
            "stale",
            "no pending",
            "targets another",
        )
    ):
        return prefix + (
            "la selección ya no coincide con la sesión actual. "
            "Vuelve a seleccionar el personaje; si persiste, reconecta."
        )
    return _retry_message(action, action_text)
