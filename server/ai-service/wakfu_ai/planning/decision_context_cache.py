"""Bounded, decision-local reuse of verified context and exact-source metadata."""
from collections import OrderedDict
from copy import deepcopy

from ..context.native_graph_parts import load_graph
from ..native.native_deadline import check


class DecisionContextCache:
    """Never rebind a source-bound certificate to a different receipt.

    A cache belongs to one search and one store. Graphs have already passed
    complete validation and remain private planner inputs. Plain metadata and
    response dictionaries are copied on both insertion and return.
    """

    def __init__(
        self,
        store,
        *,
        graph_loader=load_graph,
        max_graphs=8,
        max_nodes=200000,
        max_repertoires=128
    ):
        if any(
            type(value) is not int or value < 1
            for value in (max_graphs, max_nodes, max_repertoires)
        ):
            raise ValueError("Invalid decision context cache bounds")
        self.store, self.graph_loader = store, graph_loader
        self.max_graphs, self.max_nodes = max_graphs, max_nodes
        self.max_repertoires = max_repertoires
        self._graphs, self._plain, self._repertoires = OrderedDict(), {}, OrderedDict()
        self._nodes = 0
        self.metrics = dict(
            graphHits=0,
            graphMisses=0,
            plainHits=0,
            repertoireHits=0,
            repertoireMisses=0,
        )

    @staticmethod
    def _source(state, actor_id):
        if not isinstance(state, dict):
            return None
        key = state.get("key")
        if not isinstance(key, str) or not key or type(actor_id) is not int:
            return None
        if state.get("runtimeIdentity") is not None and not isinstance(
            state["runtimeIdentity"], str
        ):
            return None
        if (
            state.get("stateRevision") is not None
            and type(state["stateRevision"]) is not int
        ):
            return None
        return (key, state.get("runtimeIdentity"), state.get("stateRevision"), actor_id)

    def get_repertoire(self, state, actor_id):
        check()
        key = self._source(state, actor_id)
        if key is None or key not in self._repertoires:
            self.metrics["repertoireMisses"] += 1
            return None
        value = self._repertoires[key]
        self._repertoires.move_to_end(key)
        self.metrics["repertoireHits"] += 1
        result = deepcopy(value)
        check()
        return result

    def put_repertoire(self, state, actor_id, value):
        check()
        key = self._source(state, actor_id)
        if key is None:
            return
        private = deepcopy(value)
        check()
        self._repertoires[key] = private
        self._repertoires.move_to_end(key)
        while len(self._repertoires) > self.max_repertoires:
            self._repertoires.popitem(last=False)

    def graph(self, digest):
        check()
        if digest in self._graphs:
            self._graphs.move_to_end(digest)
            self.metrics["graphHits"] += 1
            return self._graphs[digest]
        self.metrics["graphMisses"] += 1
        graph = self.graph_loader(self.store, digest)
        check()
        count = len(graph.nodes)
        if count <= self.max_nodes:
            self._graphs[digest] = graph
            self._nodes += count
            while len(self._graphs) > self.max_graphs or self._nodes > self.max_nodes:
                old_digest, old_graph = self._graphs.popitem(last=False)
                self._nodes -= len(old_graph.nodes)
                self._plain.pop(old_digest, None)
        return graph

    def plain(self, digest):
        check()
        if digest in self._plain:
            self.metrics["plainHits"] += 1
            self._graphs.move_to_end(digest)
            result = deepcopy(self._plain[digest])
            check()
            return result
        graph = self.graph(digest)
        value = graph.plain(graph.data["root"])
        check()
        if digest in self._graphs:
            self._plain[digest] = deepcopy(value)
            check()
        return value
