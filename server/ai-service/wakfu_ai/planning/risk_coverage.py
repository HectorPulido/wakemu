"""Do not reward alternatives whose rival response was never explored."""


def comparable_bounds(forecasts):
    """Impute observed risk only for incomplete, unexpanded responses.

    A missing response is not evidence of safety. This is conservative
    ranking, not an invented native damage outcome or a completeness claim.
    """
    observed = {}
    for forecast in forecasts:
        for rival in forecast.get("rivals", []):
            identity = rival["actorId"]
            observed[identity] = max(
                observed.get(identity, 0), rival.get("knownLowerBound", 0)
            )
    bounds = []
    for forecast in forecasts:
        bound = forecast["knownLowerBound"]
        for rival in forecast.get("rivals", []):
            if not rival.get("complete", False) and not rival.get("expanded", 0):
                known = rival.get("knownLowerBound", 0)
                bound += max(0, observed[rival["actorId"]] - known)
        bounds.append(bound)
    return bounds
