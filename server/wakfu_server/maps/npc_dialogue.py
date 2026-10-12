"""Native NPC dialogue catalog and authoritative, explicit dialogue sessions.

Native node IDs never imply graph edges. Graphs must come from verified server
contracts. This module does not execute client Lua or grant quest rewards.
"""
from functools import lru_cache
import struct

OPEN_REQUEST = 12535
CHOICE_REQUEST = 12058
OPEN_RESPONSE = 12969
NODE_RESPONSE = 12218
NPC_SPEAKER = 2


@lru_cache(maxsize=1)
def catalog():
    from .npc_catalog import document

    data = document("npc_dialogues")
    data["node_index"] = {int(node["id"]): node for node in data["nodes"]}
    return data


def decode_request(opcode, body):
    if opcode == OPEN_REQUEST and len(body) == 13:
        node_id, speaker_type, speaker_id = struct.unpack(">ibq", body)
        return {
            "node_id": node_id,
            "speaker_type": speaker_type,
            "speaker_id": speaker_id,
        }
    if opcode == CHOICE_REQUEST and len(body) == 8:
        node_id, choice_id = struct.unpack(">ii", body)
        return {"node_id": node_id, "choice_id": choice_id}
    raise ValueError("Malformed or unsupported NPC dialogue request")


class DialogueSession:
    """One player's offered node, bound to a server-authorized nearby NPC.

    authorize_node and authorize_choice must evaluate native criteria against
    authoritative player state. Nonempty criteria fail closed by default.
    A graph maps (node_id, choice_id) to target node ID or None for closing.
    """

    def __init__(
        self, nodes=None, graph=None, authorize_node=None, authorize_choice=None
    ):
        self.nodes = catalog()["node_index"] if nodes is None else nodes
        self.graph = {} if graph is None else graph
        self.authorize_node = authorize_node or (lambda node: not node.get("criteria"))
        self.authorize_choice = authorize_choice or (
            lambda choice: not choice.get("criteria")
        )
        self.node_id = None
        self.speaker_id = None
        self.authorize_speaker = None

    def _node(self, node_id):
        node = self.nodes.get(node_id)
        if node is None or not self.authorize_node(node):
            raise ValueError("Unknown or unavailable dialogue node")
        return node

    def open(self, node_id, speaker_id, authorize_speaker, *, speaker_type=NPC_SPEAKER):
        if type(speaker_type) is not int or speaker_type not in (1, NPC_SPEAKER):
            raise ValueError("Unsupported native dialogue speaker type")
        self._node(node_id)
        if not authorize_speaker(speaker_id, node_id):
            raise ValueError("NPC is unavailable or outside interaction range")
        payload = struct.pack(">ibq", node_id, speaker_type, speaker_id)
        self.node_id, self.speaker_id = node_id, speaker_id
        self.authorize_speaker = authorize_speaker
        return OPEN_RESPONSE, payload

    def choose(self, node_id, choice_id):
        if self.node_id is None or node_id != self.node_id:
            raise ValueError("Stale or unsolicited dialogue choice")
        if not self.authorize_speaker(self.speaker_id, node_id):
            self.close()
            raise ValueError("NPC is no longer available or in interaction range")
        node = self._node(node_id)
        # Native UI emits -1 for a terminal node; -2 only advances local text.
        if choice_id == -1 and not node["choices"]:
            self.close()
            return None
        choice = next((row for row in node["choices"] if row["id"] == choice_id), None)
        if choice is None or not self.authorize_choice(choice):
            raise ValueError("Dialogue choice was not offered")
        edge = (node_id, choice_id)
        if edge not in self.graph:
            raise ValueError("Native server dialogue transition is not accredited")
        target = self.graph[edge]
        if target is None:
            self.close()
            return None
        if target == 0:
            # Native captured terminal responses explicitly carry node zero.
            self.close()
            return NODE_RESPONSE, struct.pack(">i", 0)
        self._node(target)
        payload = struct.pack(">i", target)
        self.node_id = target
        return NODE_RESPONSE, payload

    def close(self):
        self.node_id = None
        self.speaker_id = None
        self.authorize_speaker = None
