"""Select one reviewed native greeting using its unchanged owned predicates.

Alternative native roots can distinguish citizenship, gender or quest state.
The reconstructed publication supplies the finite reviewed root set, while the
native node criteria and server-owned query context remain authoritative. An
ambiguous set never gains an order-based or unconditional fallback.
"""


def validate(roots, nodes):
    if (
        type(roots) is not list
        or not roots
        or any(type(root) is not int or root <= 0 for root in roots)
        or len(set(roots)) != len(roots)
        or any(root not in nodes for root in roots)
    ):
        raise ValueError("Invalid reviewed native greeting roots")
    return tuple(roots)


def select(roots, nodes, *, available):
    matches = []
    for root in validate(roots, nodes):
        result = available(nodes[root]["criteria"])
        if type(result) is not bool:
            raise ValueError("Native greeting lacks boolean predicate authority")
        if result:
            matches.append(root)
    if len(matches) != 1:
        raise ValueError("Native greeting requires exactly one eligible root")
    return matches[0]
