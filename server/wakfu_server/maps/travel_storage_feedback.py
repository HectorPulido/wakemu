"""Explain rejected travel and account-chest access without exposing SQL text."""
import struct

from wakfu_server.ecology_feedback import information
from wakfu_server.player_action_feedback import failure_message


def rejection(action, error):
    """Return native information349; this never retries or mutates an action."""
    if action not in ("transport", "chest_open"):
        raise ValueError("Unsupported travel/storage feedback action")
    reason = str(error).casefold()
    database_error = type(error).__module__.startswith(("psycopg", "psycopg_pool"))
    if action == "transport":
        if not database_error and (
            "too far" in reason or "source interaction not allowed" in reason
        ):
            text = (
                "No se puede viajar: acércate al acceso en el mapa actual "
                "y vuelve a elegir el destino."
            )
        elif not database_error and any(
            part in reason
            for part in (
                "unknown zaap destination",
                "foreign-map zaap",
                "unknown native teleporter",
            )
        ):
            text = (
                "No se puede viajar: el acceso o destino no está disponible desde "
                "tu posición actual. Reabre el menú y elige un destino conocido."
            )
        else:
            text = failure_message("transport", error)
    elif database_error:
        text = (
            "No se pudo abrir el cofre en este momento. Cierra su ventana y "
            "vuelve a abrirlo. Si persiste, informa del error."
        )
    elif "too far" in reason:
        text = "No se puede abrir el cofre: acércate a él y vuelve a intentarlo."
    elif "owner outside combat" in reason or "foreign or unknown" in reason:
        text = (
            "No se puede abrir el cofre: usa el cofre de tu cuenta dentro de tu "
            "propio merkasaco, fuera de combate. Un visitante no puede abrirlo."
        )
    elif "session" in reason or "stale" in reason:
        text = (
            "No se puede abrir el cofre: la selección de personaje cambió. "
            "Vuelve a seleccionar tu personaje y abre de nuevo su cofre."
        )
    else:
        text = (
            "No se pudo abrir el cofre. Vuelve a acercarte al cofre de tu "
            "propio merkasaco y ábrelo de nuevo. Si persiste, informa del error."
        )
    return information(text)


def blocked_world_rejection(opcode, body):
    """Explain only travel/account-chest requests at the existing combat gate."""
    if opcode in (13686, 12296):
        return rejection(
            "transport", ValueError("World action unavailable during combat")
        )
    if (
        opcode == 12870
        and isinstance(body, bytes)
        and len(body) == 12
        and struct.unpack_from(">HH", body, 8) == (12, 0)
    ):
        return rejection(
            "chest_open", ValueError("Chest requires its owner outside combat")
        )
    return None
