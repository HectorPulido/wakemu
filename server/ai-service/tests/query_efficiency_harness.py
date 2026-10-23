"""Deterministic fixture comparisons, never a native wall-time benchmark."""
from collections import Counter, deque
from copy import deepcopy
import hashlib
import inspect
import json

from wakfu_ai.planning import query_search


def _previous_prune(frames, limit, actor_id, support_reference=None):
    """Exact pre-fix frontier selection, retained only as a test ablation."""
    branches = [frame for frame in frames if frame["depth"] != 0]
    selected = query_search._diverse_beam(
        [frame["node"] for frame in branches], limit, actor_id, support_reference
    )
    retained = {id(node) for node in selected}
    return deque(
        frame
        for frame in frames
        if frame["depth"] == 0 or id(frame["node"]) in retained
    )


def make_search(*, preview_reuse=True, frontier_reuse=True, candidate_factory=None):
    """Isolate the two fixes while retaining all current scoring and rules.

    This reconstructs an ablation, not a historical release: both variants
    use today's planner except for the explicitly disabled corrections.
    No production module globals are replaced.
    """
    source = inspect.getsource(query_search.search)
    namespace = dict(vars(query_search))
    if not preview_reuse:
        marker = "if parent is node and tried == action"
        if source.count(marker) != 1:
            raise AssertionError("Warm-preview ablation no longer matches source")
        source = source.replace(
            marker, "if False and parent is node and tried == action"
        )
        generic_marker = 'preview_cache_capacity = min(256, limits["nodes"])'
        if source.count(generic_marker) != 1:
            raise AssertionError("General preview ablation no longer matches source")
        source = source.replace(generic_marker, "preview_cache_capacity = 0")
    if not frontier_reuse:
        namespace["_prune_frontier"] = _previous_prune
    if candidate_factory is not None:
        namespace["candidates"] = candidate_factory
    exec(compile(source, __file__, "exec"), namespace)
    function = namespace["search"]
    function.fixture_variant = dict(
        previewReuse=preview_reuse, frontierReuse=frontier_reuse
    )
    function.fixture_source = source
    return function


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def measure(session, search_function, *, query_budget=None):
    """Measure unique fixture transitions under an optional query-count cap.

    Public receipt keys/revisions are synthetic counters in these fixtures,
    not game facts. Retain every other public field, complete native graph
    digest and the fixture's hidden repertoire-use flag in runtime identity.
    This identity is local to one fixture decision, never cross-fight reuse.

    With a query cap, every exchange costs one abstract time unit. Exact
    binary clock ticks eliminate wall-time noise. The production owner deadline is
    used to enforce that cap; this is not a claim that all queries cost equal
    milliseconds on a real server.
    """

    def stamp(key):
        row = session.states[key]
        public = row["public"]
        facts = {
            name: value
            for name, value in public.items()
            if name not in {"key", "stateRevision", "runtimeIdentity"}
        }
        digest = hashlib.sha256(
            _canonical(dict(public=facts, used=row["used"])).encode()
        ).hexdigest()
        public["runtimeIdentity"] = digest
        return digest

    root_identity = stamp(session.envelope["rootState"])
    if query_budget is not None:
        if type(query_budget) is not int or query_budget < 2:
            raise ValueError("Query cap must allow root lookup and one preview")
        session.envelope["nativeBudgetMs"] = query_budget * 1000 / 1024
        session.envelope["policy"].update(
            commitReserveMs=0, searchTimeFraction=1, rivalSearchReserveMs=0
        )
    elapsed, trace = 0, []
    counts, previews = Counter(), Counter()
    outcomes, sources = set(), set()
    coroutine = search_function(
        session.envelope,
        session.store,
        clock=lambda: elapsed / 1024 if query_budget is not None else 0,
    )
    response = None
    while True:
        try:
            query = next(coroutine) if response is None else coroutine.send(response)
        except StopIteration as completed:
            result = completed.value
            break
        source = stamp(query["state"])
        sources.add(source)
        counts[query["operation"]] += 1
        if query["operation"] == "preview":
            previews[(source, _canonical(query["action"]))] += 1
        response = session.request(query)
        outcome = None
        if query["operation"] == "preview" and response["supported"]:
            outcome = stamp(response["result"]["key"])
            response["result"]["runtimeIdentity"] = outcome
            if outcome != root_identity:
                outcomes.add(outcome)
        elapsed += 1
        if query_budget is not None:
            response["nativeBudgetMs"] = max(0, query_budget - elapsed) * 1000 / 1024
        trace.append(
            dict(
                operation=query["operation"],
                source=source,
                action=deepcopy(query.get("action")),
                supported=response["supported"],
                outcome=outcome,
            )
        )
    if query_budget is not None and elapsed > query_budget:
        raise AssertionError("Planner exceeded the deterministic exchange cap")
    return dict(
        result=result,
        queries=dict(counts),
        totalQueries=elapsed,
        uniquePreviews=len(previews),
        duplicatePreviews=sum(previews.values()) - len(previews),
        uniqueAlternatives=len(outcomes),
        uniqueSources=len(sources),
        trace=trace,
    )
