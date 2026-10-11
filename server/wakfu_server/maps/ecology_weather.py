"""External weather simulation and bounded world publication contracts.

Proposals carry trusted service-produced forecast bytes, never client input.
Database authority is reloaded before each publication; no socket operation
occurs inside a transaction. Delivery remains at-least-once, not a client ACK.
"""
from . import territory_weather as weather
from . import territory_weather_forecast as forecast


def prepare(store, snapshot, limit=16):
    """Advance durable weather and prepare JSON-safe publication proposals."""
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("Invalid ecology weather batch size")
    epoch = snapshot.get("world_epoch", snapshot.get("epoch"))
    weather.advance_due(store, limit=limit)
    proposals = []
    for event in weather.pending_publications(store, limit=limit):
        proposals.append(
            dict(
                domain="weather",
                operation="publish",
                world_epoch=epoch,
                event={
                    key: event[key]
                    for key in ("map_id", "instance_id", "region_id", "revision")
                },
            )
        )
    remaining = limit - len(proposals)
    if remaining:
        for event in forecast.pending_publications(store, limit=remaining):
            try:
                payload = forecast.packet_for_territory(store, **event)
            except ValueError as error:
                if str(error) == "Weather forecast policy was superseded":
                    continue
                raise
            proposals.append(
                dict(
                    domain="weather",
                    operation="forecast_publish",
                    world_epoch=epoch,
                    event=event,
                    payload_hex=payload.hex(),
                )
            )
    return proposals


def apply(store, world, proposal):
    """Reload one exact current event, publish, then conditionally acknowledge."""
    if type(proposal) is not dict or proposal.get("domain") != "weather":
        raise ValueError("Invalid ecology weather proposal")
    event = proposal.get("event")
    if type(event) is not dict:
        raise ValueError("Invalid ecology weather event")
    weather._validate_scope(
        event.get("map_id"), event.get("instance_id"), event.get("region_id")
    )
    operation = proposal.get("operation")
    if operation not in ("publish", "forecast_publish"):
        raise ValueError("Invalid ecology weather operation")
    version = "revision" if operation == "publish" else "policy_version"
    if set(event) != {"map_id", "instance_id", "region_id", version}:
        raise ValueError("Invalid ecology weather event fields")
    if type(event[version]) is not int or event[version] < 1:
        raise ValueError("Invalid ecology weather event version")
    scope = (event["map_id"], event["instance_id"], event["region_id"], event[version])
    if operation == "publish":
        query = (
            "SELECT o.map_id,o.instance_id,o.region_id,o.revision,o.weather,o.native_payload "
            "FROM territory_weather_outbox o JOIN territory_weather w "
            "USING(map_id,instance_id,region_id) WHERE o.map_id=%s AND o.instance_id=%s "
            "AND o.region_id=%s AND o.revision=%s AND o.published_at IS NULL "
            "AND o.superseded_at IS NULL AND o.revision=w.revision "
            "AND o.weather=w.weather AND o.native_payload=w.native_payload"
        )
    else:
        query = (
            "SELECT o.map_id,o.instance_id,o.region_id,o.policy_version "
            "FROM territory_weather_forecast_outbox o JOIN territory_weather_forecast_policy p "
            "USING(map_id,instance_id,region_id) WHERE o.map_id=%s AND o.instance_id=%s "
            "AND o.region_id=%s AND o.policy_version=%s AND o.published_at IS NULL "
            "AND o.superseded_at IS NULL AND o.policy_version=p.policy_version"
        )
    with store.connection() as db:
        row = db.execute(query, scope).fetchone()
    if row is None:
        return dict(status="stale", published=0)
    current = dict(row)
    if operation == "publish":
        weather.publish_to_world(world, current)
        acknowledged = weather.acknowledge_publication(store, current)
    else:
        encoded = proposal.get("payload_hex")
        if type(encoded) is not str or len(encoded) > 131072:
            raise ValueError("Invalid prepared forecast payload")
        try:
            payload = bytes.fromhex(encoded)
        except ValueError as error:
            raise ValueError("Invalid prepared forecast payload") from error
        forecast.publish_to_world(store, world, current, prepared_payload=payload)
        acknowledged = forecast.acknowledge_publication(store, current)
    return dict(
        status="applied" if acknowledged else "stale", published=int(acknowledged)
    )
