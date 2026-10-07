"""Beam search with an injected native forecast adapter and utility callback."""
import time


def bounded_search(adapter, root_key, limits, deadline, evaluate, actor_id):
    # (score, action count, stable transition sequence) produces deterministic
    # ties, avoids zero-cost loops and preserves alternatives by intent/target.
    baseline = dict(
        score=0.0,
        components=evaluate(root_key)[1],
        intent="end_turn",
        target=None,
        actions=[],
        ids=(),
        key=root_key,
        visited=frozenset({root_key}),
    )
    beam, candidates = [baseline], [baseline]
    expanded, timed_out = 0, False
    for _ in range(limits["depth"]):
        following = []
        for node in beam:
            for transition in adapter.legal_actions(node["key"]):
                if expanded >= limits["nodes"] or time.monotonic() >= deadline:
                    timed_out = time.monotonic() >= deadline
                    break
                destination = adapter.preview(node["key"], transition)
                if destination in node["visited"]:
                    continue
                expanded += 1
                score, components, intent, target = evaluate(destination)
                option = dict(
                    score=score,
                    components=components,
                    intent=intent,
                    target=target,
                    actions=node["actions"] + [transition["action"]],
                    ids=node["ids"] + (transition["id"],),
                    key=destination,
                    visited=node["visited"] | {destination},
                )
                candidates.append(option)
                if transition["action"]["type"] != "end_turn" and not adapter.terminal(
                    destination, actor_id
                ):
                    following.append(option)
            if expanded >= limits["nodes"] or timed_out:
                break
        if not following or expanded >= limits["nodes"] or timed_out:
            break
        following.sort(key=lambda n: (-n["score"], len(n["actions"]), n["ids"]))
        unique, seen = [], set()
        # World state keys include usage/cooldowns/conditions/direction, so
        # deduplication never merges two equal-HP states with different rules.
        for option in following:
            if option["key"] not in seen:
                seen.add(option["key"])
                unique.append(option)
        diverse, represented = [], set()
        for option in unique:
            category = (option["intent"], option["target"])
            if category not in represented:
                represented.add(category)
                diverse.append(option)
        beam = (diverse + [n for n in unique if n not in diverse])[: limits["beam"]]
    candidates.sort(key=lambda n: (-n["score"], len(n["actions"]), n["ids"]))
    return candidates, expanded, timed_out
