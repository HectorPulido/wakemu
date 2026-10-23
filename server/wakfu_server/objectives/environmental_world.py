"""Post-commit environmental publication for one authenticated World connection.

Only qualified installed native decoder contracts are encoded here.
An absent native profile never becomes an invented challenge definition.
"""
import struct


def _integer(value, bits, name, *, lower=None):
    minimum = -(1 << (bits - 1)) if lower is None else lower
    if type(value) is not int or not minimum <= value < 1 << (bits - 1):
        raise ValueError(f"Invalid native environmental {name}")
    return value


def initial_packet(
    *,
    state,
    challenge_id,
    secondary_id,
    remaining_ms,
    native_time,
    protector_id,
    challenge_value,
    available,
    variables,
    objective_ids=None,
):
    """cAH12549: exact30-byte header followed by active objective IDs."""
    if type(state) is not int or state not in (-1, 0, 1, 2, 3):
        raise ValueError("Invalid native environmental initial state")
    if type(available) is not bool or not isinstance(variables, (tuple, list)):
        raise ValueError("Invalid native environmental availability or variables")
    # The legacy argument name is retained for direct codec callers. Native
    # cAH does not initialize the indexed variable map.
    values = [
        _integer(value, 32, "objective id")
        for value in (variables if objective_ids is None else objective_ids)
    ]
    return 12549, struct.pack(
        ">biiiqiiB",
        state,
        _integer(challenge_id, 32, "challenge id"),
        _integer(secondary_id, 32, "secondary id"),
        _integer(remaining_ms, 32, "remaining milliseconds", lower=0),
        _integer(native_time, 64, "time"),
        _integer(protector_id, 32, "protector id"),
        _integer(challenge_value, 32, "challenge value"),
        int(available),
    ) + b"".join(struct.pack(">i", value) for value in values)


def status_packet(*, state, secondary_id, remaining_ms, native_time):
    """cAK12276 applies state/countdown; its other fields are not replay guards."""
    if type(state) is not int or state not in (0, 1, 2, 3):
        raise ValueError("Invalid native environmental status state")
    return 12276, struct.pack(
        ">biiq",
        state,
        _integer(secondary_id, 32, "secondary id"),
        _integer(remaining_ms, 32, "remaining milliseconds", lower=0),
        _integer(native_time, 64, "time"),
    )


def variable_packet(challenge_id, variable_index, value):
    """cAM12124 updates an explicitly indexed installed challenge variable."""
    return 12124, struct.pack(
        ">ibq",
        _integer(challenge_id, 32, "challenge id"),
        _integer(variable_index, 8, "variable index", lower=0),
        _integer(value, 64, "variable value"),
    )


def objective_packet(challenge_id, objective_id):
    """cAE13538 marks a native objective completed; it does not activate it."""
    return 13538, struct.pack(
        ">ii",
        _integer(challenge_id, 32, "challenge id"),
        _integer(objective_id, 32, "objective id"),
    )


def notification_packet(challenge_id):
    return 12175, struct.pack(">i", _integer(challenge_id, 32, "challenge id"))


def challenge_value_packet(value):
    # cAG updates the currently displayed challenge; it has no identity field.
    return 12361, struct.pack(">i", _integer(value, 32, "challenge value"))


def live_rank_packet(rank):
    """cAJ13828 updates the selected competitive context directly (one-based)."""
    if type(rank) is not int or rank < -2 or rank == 0:
        raise ValueError("Invalid native environmental live rank")
    return 13828, struct.pack(">h", _integer(rank, 16, "live rank"))


def challenge_list_packet(challenge_id, values, variables, *, optional_value=None):
    """cAF13955: bounded signed-byte list and indexed int64 variable tail."""
    if not isinstance(values, (tuple, list)) or not isinstance(
        variables, (tuple, list)
    ):
        raise ValueError("Invalid native environmental list")
    if len(values) > 127 or len(variables) > 4096:
        raise ValueError("Native environmental list exceeds its wire bounds")
    body = struct.pack(">ib", _integer(challenge_id, 32, "challenge id"), len(values))
    body += b"".join(
        struct.pack(">i", _integer(value, 32, "list value")) for value in values
    )
    body += struct.pack(">b", int(optional_value is not None))
    if optional_value is not None:
        body += struct.pack(">i", _integer(optional_value, 32, "optional value"))
    body += struct.pack(">i", len(variables))
    indices = set()
    for row in variables:
        index = _integer(row["variable_index"], 8, "variable index", lower=0)
        if index in indices:
            raise ValueError("Duplicate native environmental variable index")
        indices.add(index)
        body += struct.pack(">bq", index, _integer(row["value"], 64, "variable value"))
    return 13955, body


def _projection(instance):
    profile = instance.get("native_publication")
    if profile is None:
        return None
    names = profile["variable_names"]
    variables = instance["variables"]
    if (
        not isinstance(names, (list, tuple))
        or any(not isinstance(name, str) or not name for name in names)
        or len(set(names)) != len(names)
        or not isinstance(variables, (list, tuple))
        or len(variables) != len(names)
        or any(
            type(row["variable_index"]) is not int or row["variable_index"] != index
            for index, row in enumerate(variables)
        )
        or profile["challenge_id"] != instance["native_scenario_id"]
        or profile["protector_id"] != instance["protector_id"]
    ):
        raise ValueError("Environmental display differs from its frozen native profile")
    deadline = instance.get("countdown_deadline_ms", instance["deadline_ms"])
    now = instance["now_ms"]
    started = instance.get("started_at_ms")
    if (
        type(deadline) is not int
        or type(now) is not int
        or type(started) is not int
        or started <= 0
    ):
        raise ValueError("Environmental countdown lacks its durable start/deadline")
    result = dict(
        state=profile["state_ordinal"],
        challenge_id=profile["challenge_id"],
        # cAH decodes this long as epoch start time. Zero prevents
        # the native active-model timer from being registered.
        secondary_id=profile["secondary_id"],
        native_time=started,
        protector_id=profile["protector_id"],
        remaining_ms=max(0, deadline - now),
        # cAH.eNB says that this challenge is present. False clears
        # the native context even when a completed ID is supplied.
        challenge_value=instance["challenge_value"],
        available=True,
        variables=[row["value"] for row in variables],
        objective_ids=instance.get("active_objectives", []),
    )
    initial_packet(**result)  # Validate the complete projection before any publication.
    return result


def _context_packets(projection):
    """Bind objective status and all variable values for each fresh model."""
    return [
        initial_packet(**projection),
        challenge_list_packet(
            projection["challenge_id"],
            projection["objective_ids"],
            [
                dict(variable_index=index, value=value)
                for index, value in enumerate(projection["variables"])
            ],
        ),
    ]


class SelectedEnvironmentalEvents:
    """Never acknowledge durable delivery before the selected lease receives it."""

    def __init__(self, *, hero_template=None, roster_template=None, groups=None):
        self._identity = None
        self._scope = None
        self._published = None
        self.claimed_character = None
        self._hero_template = hero_template
        self._roster_template = roster_template
        self._groups = groups

    def refresh(
        self,
        store,
        world,
        account_id,
        generation,
        character_id,
        *,
        location,
        ready,
        checkpoint,
        now_ms=None,
    ):
        from . import environmental_service
        from .environmental_presence import capture, current as presence_current

        self.claimed_character = None
        if type(ready) is not bool:
            raise ValueError("Explicit environmental scene readiness required")
        if not ready:
            return False
        occupied = capture(location["map_id"], location["instance_id"], world=world)
        if occupied is None:
            return False
        identity = (account_id, generation, character_id)
        scope = tuple(location[key] for key in ("map_id", "instance_id", "region_id"))
        if not store.current_character_session(*identity):
            raise ValueError(
                "Environmental publication belongs to a replaced selection"
            )
        if self._identity != identity or self._scope != scope:
            # The position registry is authoritative while walking. Persist it
            # only on scope admission, rather than flushing every native step.
            checkpoint()
        options = {} if self._groups is None else dict(groups=self._groups)
        snapshot = environmental_service.refresh(
            store, *identity, location=dict(location), now_ms=now_ms, **options
        )
        if snapshot.get("inactive_scope") or not presence_current(
            occupied, location["map_id"], location["instance_id"]
        ):
            return False
        group_publications = 0
        if self._groups is not None:
            from .environmental_group_publication import publish

            group_publications = publish(
                store,
                world,
                self._groups,
                map_id=location["map_id"],
                instance_id=location["instance_id"],
                now_ms=environmental_service._clock(store, now_ms),
            )
        resource_publications = snapshot.get("resource_publications", ())
        if resource_publications:
            resource_packets = tuple(
                packet for row in resource_publications for packet in row["packets"]
            )
            sent = world.emit_location_batch(
                location["map_id"],
                location["instance_id"],
                resource_packets,
                require_all=True,
            )
            if not sent:
                return False
            environmental_service.acknowledge_resources(
                store,
                *identity,
                location=location,
                publication_ids=[
                    row["publication_id"] for row in resource_publications
                ],
                now_ms=now_ms,
            )
        candidates = [(row, _projection(row)) for row in snapshot["instances"]]
        candidates = [
            (row, projection)
            for row, projection in candidates
            if projection is not None
        ]
        if len(candidates) > 1:
            raise ValueError(
                "Multiple environmental displays need an explicit native list contract"
            )
        current = candidates[0][1] if candidates else None
        current_instance = candidates[0][0]["instance_id"] if candidates else None
        current_deadline = (
            candidates[0][0].get(
                "countdown_deadline_ms", candidates[0][0]["deadline_ms"]
            )
            if candidates
            else None
        )
        current_rank = candidates[0][0].get("live_rank") if candidates else None
        deliveries = snapshot["deliveries"]
        current_result = any(
            delivery.get("kind") == "completed"
            and delivery.get("character_id") == character_id
            and delivery.get("instance_id") == current_instance
            and delivery.get("result_view") is not None
            and not delivery.get("deferred_selected_result")
            and any(packet[0] == 13263 for packet in delivery["packets"])
            for delivery in deliveries
        )
        # Native results mark success before closing the context themselves.
        # A terminal header before that flag would instead announce failure.
        current_header = (
            dict(current, state=1)
            if current_result and current is not None
            else current
        )
        packets = []
        previous = (
            self._published
            if self._identity == identity and self._scope == scope
            else None
        )
        if current is not None:
            event_identity = (
                current_instance,
                current["challenge_id"],
                current["secondary_id"],
                current["protector_id"],
            )
            if (
                previous is None
                or getattr(self, "_published_event", None) != event_identity
            ):
                packets.extend(_context_packets(current_header))
            else:
                # cAK RUNNING always replays the native start animation/toast.
                # The client owns its countdown after initialization; only a
                # genuine lifecycle transition needs a new status packet.
                if not (current_result and current["state"] == 2) and (
                    current["state"] != previous["state"]
                    or current_deadline != getattr(self, "_published_deadline", None)
                ):
                    packets.append(
                        status_packet(
                            **{
                                key: current[key]
                                for key in (
                                    "state",
                                    "secondary_id",
                                    "remaining_ms",
                                    "native_time",
                                )
                            }
                        )
                    )
                packets.extend(
                    variable_packet(current["challenge_id"], index, value)
                    for index, value in enumerate(current["variables"])
                    if index >= len(previous["variables"])
                    or value != previous["variables"][index]
                )
                if current["challenge_value"] != previous["challenge_value"]:
                    packets.append(challenge_value_packet(current["challenge_value"]))
        elif not snapshot["instances"] and self._published is not None:
            packets.append(
                initial_packet(
                    state=3,
                    challenge_id=-1,
                    secondary_id=0,
                    remaining_ms=0,
                    native_time=0,
                    protector_id=-1,
                    challenge_value=0,
                    available=False,
                    variables=[],
                )
            )
        # Rewards/results remain durable service deliveries, not inferred from
        # the presence of a completion UI or an entitlement reservation.
        header_packets, packets = packets, []
        historical_results = []
        keys = []
        hero_refresh = False
        for delivery in deliveries:
            if delivery.get("deferred_selected_result"):
                if (
                    delivery.get("kind") != "completed"
                    or delivery.get("character_id") == character_id
                ):
                    raise ValueError("Invalid deferred environmental selected result")
                # Do not acknowledge a hero's native result through its leader.
                # Its separate absolute reward/entity delivery remains eligible.
                continue
            key = delivery["delivery_key"]
            if not isinstance(key, str) or not key or key in keys:
                raise ValueError("Invalid environmental delivery identity")
            hero = delivery.get("hero_character")
            if hero is not None:
                from wakfu_server.characters import hero_wire

                if (
                    self._hero_template is None
                    or hero["account_id"] != account_id
                    or hero["id"] == character_id
                    or hero["id"] != delivery["character_id"]
                ):
                    raise ValueError(
                        "Environmental hero publication lacks its owned native identity"
                    )
                # Heroes follow the live main; their older persisted tile is
                # never allowed to move the loaded native entity backwards.
                hero = dict(
                    hero,
                    **{
                        key: location[key]
                        for key in ("map_id", "instance_id", "x", "y", "z")
                        if key in location
                    },
                )
                packets.extend(
                    (
                        hero_wire.refresh(self._hero_template, hero),
                        hero_wire.statistics(hero),
                    )
                )
                hero_refresh = True
            result_view = delivery.get("result_view")
            target_packets = packets
            if result_view is not None and delivery["instance_id"] != current_instance:
                # cio applies a result to the global challenge state. Hydrate
                # its original context first, then restore the current event
                # after historical results, including same-definition cycles.
                context = _projection(result_view)
                if any(packet[0] == 13263 for packet in delivery["packets"]):
                    context = dict(context, state=1)
                historical_results.extend(_context_packets(context))
                target_packets = historical_results
            for opcode, payload in delivery["packets"]:
                if type(opcode) is not int or type(payload) is not bytes:
                    raise ValueError("Invalid environmental durable packet")
                target_packets.append((opcode, payload))
            keys.append(key)
        if hero_refresh and self._roster_template is not None:
            from wakfu_server import wire

            packets.append(
                (
                    23548,
                    wire.character_list(
                        self._roster_template, account_id, store.characters(account_id)
                    ),
                )
            )
        if historical_results and current is not None:
            header_packets = _context_packets(current_header)
        packets = historical_results + header_packets + packets
        if current_rank is not None and (
            previous is None
            or getattr(self, "_published_event", None) != event_identity
            or current_rank != getattr(self, "_published_rank", None)
            or current["challenge_value"] != previous["challenge_value"]
            or historical_results
        ):
            # This packet has no event ID: send only after its selected current
            # context has been initialized/restored, never into a historical one.
            packets.append(live_rank_packet(current_rank))
        if not store.current_character_session(*identity):
            raise ValueError(
                "Environmental selection changed after snapshot settlement"
            )
        if packets and not world.send_batch_to(
            character_id, generation, tuple(packets)
        ):
            return False
        if keys:
            environmental_service.acknowledge(store, *identity, keys)
        self._identity, self._scope, self._published = identity, scope, current
        self._published_event = (
            None
            if current is None
            else (
                current_instance,
                current["challenge_id"],
                current["secondary_id"],
                current["protector_id"],
            )
        )
        self._published_deadline = current_deadline
        self._published_rank = current_rank
        self.claimed_character = snapshot.get("character")
        return bool(packets or resource_publications or group_publications)
