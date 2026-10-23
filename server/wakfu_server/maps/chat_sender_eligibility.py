"""Native political and battleground sender gates, independent of recipients."""
import struct

from wakfu_server.characters import nation_state
from wakfu_server.native_world_context import is_battleground


def require(opcode, *, character, nation_id):
    """Use the same trusted state as native identity; never request privileges."""
    if opcode == 12387:
        # The native command requires both citizenship and fsI office1..10.
        # Current ordinary citizenship publishes office0; neither account admin
        # status nor a client-supplied rank may replace government authority.
        state = nation_state.synchro(character)
        if type(state) is not bytes or len(state) != 27:
            raise ValueError("Missing authoritative political sender state")
        office = struct.unpack_from(">q", state)[0]
        if nation_id not in nation_state.NATION_IDS - {0} or office not in range(1, 11):
            raise ValueError("El canal político requiere un cargo de gobierno vigente.")
    elif opcode == 13702:
        # Native arM is the installed map/world reference, not a private scene
        # instance ID, combat type or an actor's PvP rank.
        if not is_battleground(character.get("map_id")):
            raise ValueError(
                "El canal de batalla requiere un mapa de campo de batalla."
            )
