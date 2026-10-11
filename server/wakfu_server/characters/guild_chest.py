"""Guild-shared item custody using the existing account chest transfer engine.

Lock order is acting session/character, guild aggregate, then compartments.
Native dispatch must additionally bind operations to an authorized world object.
Every request rechecks current membership and rights; opening is not authority.
"""
from copy import deepcopy

from psycopg.types.json import Jsonb

from .guild_service import GuildService
from wakfu_server import haven_chest as custody


def _integer(value, label, minimum=0, maximum=2**63 - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid guild chest " + label)
    return value


def _start(store, db, account, generation, character, expected_guild_id=None):
    service = GuildService(store)
    policy = service._start(db, account, generation, character)
    guild = service._guild(db, character)
    if expected_guild_id is not None and guild["id"] != _integer(
        expected_guild_id, "expected guild", 1
    ):
        raise ValueError("Guild chest membership changed")
    chest_policy = policy.get("chest", {})
    if chest_policy.get("enabled") is not True:
        raise ValueError("Guild chest is disabled")
    return service, guild, chest_policy


def _definition(policy, guild, compartment, *, allow_locked=False):
    _integer(compartment, "compartment", maximum=3)
    definition = policy.get("compartments", {}).get(str(compartment))
    if not isinstance(definition, dict):
        raise ValueError("Unknown guild chest compartment")
    _integer(definition.get("capacity"), "capacity", 40, 40)
    if not isinstance(definition.get("name"), str) or not definition["name"]:
        raise ValueError("Missing guild chest name")
    if type(definition.get("requires_unlock")) is not bool:
        raise ValueError("Missing guild compartment unlock policy")
    if (
        definition["requires_unlock"]
        and compartment not in guild["unlocked_compartments"]
        and not allow_locked
    ):
        raise ValueError("Guild chest compartment is locked")
    return definition


def _permission(db, guild, character, definition, action):
    row = db.execute(
        "SELECT r.permissions FROM guild_members m JOIN guild_ranks r "
        "ON r.guild_id=m.guild_id AND r.id=m.rank_id "
        "WHERE m.guild_id=%s AND m.character_id=%s",
        (guild["id"], character),
    ).fetchone()
    bit = definition.get("permission_bits", {}).get(action)
    if (
        row is None
        or type(bit) is not int
        or not 0 <= bit < 63
        or not row["permissions"] & (1 << bit)
    ):
        raise ValueError("Guild chest permission denied: " + action)


def _chest(db, guild, compartment, definition):
    db.execute(
        "INSERT INTO guild_chests(guild_id,compartment_id,capacity) VALUES(%s,%s,%s) "
        "ON CONFLICT DO NOTHING",
        (guild["id"], compartment, definition["capacity"]),
    )
    row = db.execute(
        "SELECT * FROM guild_chests WHERE guild_id=%s AND compartment_id=%s FOR UPDATE",
        (guild["id"], compartment),
    ).fetchone()
    # Never silently shrink or expand an occupied persistent compartment.
    if row["capacity"] != definition["capacity"]:
        raise ValueError("Guild chest capacity requires explicit migration")
    chest = dict(
        id=compartment,
        guild_id=guild["id"],
        name=definition["name"],
        capacity=row["capacity"],
        revision=row["revision"],
        items=custody._unjson(row["items"]),
    )
    _validate_chest(chest)
    return chest


def _validate_chest(chest):
    slots, identities = set(), set()
    for entry in chest["items"]:
        slot = _integer(entry["slot"], "stored slot", 0, chest["capacity"] - 1)
        identity = _integer(entry["item"]["uid"], "stored item identity", 1)
        _integer(entry["item"]["quantity"], "stored quantity", 1, 32767)
        if slot in slots or identity in identities:
            raise ValueError("Duplicate guild chest slot or item identity")
        slots.add(slot)
        identities.add(identity)


def _save(db, chest):
    from .guild_chest_wire import contents

    contents([chest])  # Reject an unpublishable compartment before committing custody.
    chest["revision"] += 1
    db.execute(
        "UPDATE guild_chests SET items=%s,revision=%s WHERE guild_id=%s AND compartment_id=%s",
        (
            Jsonb(custody._json(chest["items"])),
            chest["revision"],
            chest["guild_id"],
            chest["id"],
        ),
    )


def _receipt(db, character, key, guild, request):
    if not isinstance(key, str) or not 1 <= len(key) <= 200:
        raise ValueError("Invalid guild chest operation key")
    row = db.execute(
        "SELECT guild_id,request FROM guild_chest_receipts "
        "WHERE character_id=%s AND operation_key=%s",
        (character, key),
    ).fetchone()
    if row and (row["guild_id"] != guild["id"] or row["request"] != request):
        raise ValueError("Guild chest operation key reused with a different request")
    return row is not None


def _finish(db, character, key, guild, request):
    db.execute(
        "INSERT INTO guild_chest_receipts(character_id,operation_key,guild_id,request) "
        "VALUES(%s,%s,%s,%s)",
        (character, key, guild["id"], Jsonb(request)),
    )


def _revision(chest, expected):
    _integer(expected, "revision")
    if chest["revision"] != expected:
        raise ValueError("Guild chest changed; refresh before retrying")


def _eligible(entry):
    from wakfu_server.exchange_rules import eligibility

    binding = entry.get("metadata", {}).get("inventory_item_bindings", {})
    if not eligibility(entry["item"]["reference"], bound=binding.get("bound")):
        raise ValueError("Bound or nonexchangeable items cannot enter a guild chest")


def _requests(requests, chest, deposit):
    if (
        type(deposit) is not bool
        or not isinstance(requests, list)
        or not 1 <= len(requests) <= 128
    ):
        raise ValueError("Invalid guild chest transfer batch")
    used = set()
    for request in requests:
        if not isinstance(request, dict) or request.get("compartment") != chest["id"]:
            raise ValueError("Foreign guild chest compartment")
        identity = _integer(request.get("uid"), "item identity", 1)
        if identity in used:
            raise ValueError("Duplicate guild chest item")
        used.add(identity)
        _integer(request.get("quantity"), "quantity", 1, 32767)
        _integer(
            request.get("slot"), "slot", -1 if deposit else 0, chest["capacity"] - 1
        )
        if not deposit:
            source = next(
                (entry for entry in chest["items"] if entry["slot"] == request["slot"]),
                None,
            )
            if (
                source is None
                or source["item"]["uid"] != identity
                or source["item"]["reference"] != request.get("reference")
            ):
                raise ValueError("Guild chest withdrawal source changed or unavailable")
            _integer(request.get("container"), "destination container", 1)
            _integer(request.get("destination"), "destination position", -1, 32766)


def _character(db, account, character):
    """Read only custody fields; never reload or recalculate combat state."""
    from wakfu_server.inventory_items import load as load_inventory

    builds = {
        row["build_index"]: {"equipment": bytes(row["equipment"]).hex()}
        for row in db.execute(
            "SELECT build_index,equipment FROM character_builds "
            "WHERE character_id=%s",
            (character,),
        ).fetchall()
    }
    wallet = db.execute(
        "SELECT kamas FROM account_wallets WHERE account_id=%s", (account,)
    ).fetchone()
    return dict(
        id=character,
        account_id=account,
        builds=builds,
        inventory_items=load_inventory(db, character),
        inventory_containers=[
            dict(row)
            for row in db.execute(
                "SELECT * FROM inventory_containers WHERE character_id=%s ORDER BY kind,uid",
                (character,),
            ).fetchall()
        ],
        kamas=wallet["kamas"] if wallet else 0,
    )


def load(
    store,
    account_id,
    generation,
    character_id,
    compartment_id,
    *,
    expected_guild_id=None
):
    """Internal snapshot API; native callers also require a valid open context."""
    with store.connection() as db:
        _, guild, policy = _start(
            store, db, account_id, generation, character_id, expected_guild_id
        )
        definition = _definition(policy, guild, compartment_id)
        _permission(db, guild, character_id, definition, "view")
        return _chest(db, guild, compartment_id, definition)


def snapshot(
    store,
    account_id,
    generation,
    character_id,
    compartment_ids,
    *,
    expected_guild_id=None
):
    """Read an entire authorized storage view under one guild aggregate lock."""
    if not isinstance(compartment_ids, (list, tuple)) or not compartment_ids:
        raise ValueError("Missing guild chest compartments")
    if len(set(compartment_ids)) != len(compartment_ids):
        raise ValueError("Duplicate guild chest compartments")
    with store.connection() as db:
        _, guild, policy = _start(
            store, db, account_id, generation, character_id, expected_guild_id
        )
        chests = []
        for identity in sorted(compartment_ids):
            definition = _definition(policy, guild, identity, allow_locked=True)
            enabled = (
                not definition["requires_unlock"]
                or identity in guild["unlocked_compartments"]
            )
            try:
                _permission(db, guild, character_id, definition, "view")
            except ValueError:
                enabled = False
            if enabled:
                chests.append(
                    dict(_chest(db, guild, identity, definition), enabled=True)
                )
            else:
                chests.append(
                    dict(
                        id=identity,
                        guild_id=guild["id"],
                        name=definition["name"],
                        capacity=definition["capacity"],
                        revision=0,
                        items=[],
                        enabled=False,
                    )
                )
        state = db.execute(
            "SELECT record FROM guild_service_state WHERE guild_id=%s AND service='economy'",
            (guild["id"],),
        ).fetchone()
        money = _integer(
            state["record"].get("kamas", 0) if state else 0, "treasury balance"
        )
        if not any(chest.get("enabled") for chest in chests):
            money = 0
        return dict(chests=chests, money=money, guild_id=guild["id"])


def transfer_money(
    store,
    account_id,
    generation,
    character_id,
    compartment_id,
    amount,
    *,
    withdraw=False,
    operation_key,
    expected_guild_id=None
):
    """Native chest treasury adapter; chest and treasury rights checked atomically."""
    from . import guild_economy as economy

    _integer(amount, "money amount", 1)
    if type(withdraw) is not bool:
        raise ValueError("Invalid guild chest money direction")
    request = dict(
        operation="money",
        compartment_id=compartment_id,
        amount=amount,
        withdraw=withdraw,
    )
    with store.connection() as db:
        _, guild, policy = _start(
            store, db, account_id, generation, character_id, expected_guild_id
        )
        definition = _definition(policy, guild, compartment_id)
        for action in ("view", "withdraw" if withdraw else "deposit"):
            _permission(db, guild, character_id, definition, action)
        economic_policy = economy._policy(db, "treasury_enabled")
        economy._member(
            db,
            guild["id"],
            character_id,
            economic_policy,
            "treasury_withdraw" if withdraw else "treasury_deposit",
        )
        replay = _receipt(db, character_id, operation_key, guild, request)
        state = economy._state(db, guild["id"])
        treasury = _integer(state.get("kamas", 0), "treasury balance")
        wallet_row = db.execute(
            "SELECT kamas FROM account_wallets WHERE account_id=%s FOR UPDATE",
            (account_id,),
        ).fetchone()
        if wallet_row is None:
            raise ValueError("Account wallet does not exist")
        wallet = _integer(wallet_row["kamas"], "wallet balance")
        if not replay:
            change = -amount if withdraw else amount
            treasury = _integer(treasury + change, "treasury balance")
            wallet = _integer(wallet - change, "wallet balance")
            db.execute(
                "UPDATE account_wallets SET kamas=%s WHERE account_id=%s",
                (wallet, account_id),
            )
            state["kamas"] = treasury
            economy._save(
                db,
                guild["id"],
                state,
                "chest_money",
                dict(
                    character_id=character_id,
                    compartment_id=compartment_id,
                    withdraw=withdraw,
                    amount=amount,
                ),
            )
            _finish(db, character_id, operation_key, guild, request)
        return dict(
            character=_character(db, account_id, character_id),
            applied=not replay,
            treasury_kamas=treasury,
        )


def transfer(
    store,
    account_id,
    generation,
    character_id,
    compartment_id,
    requests,
    *,
    deposit,
    operation_key,
    expected_revision,
    expected_guild_id=None
):
    """Conserve inventory + guild custody with durable deduplication and CAS."""
    request = dict(
        operation="transfer",
        compartment_id=compartment_id,
        requests=deepcopy(requests),
        deposit=deposit,
        expected_revision=expected_revision,
    )
    with store.connection() as db:
        service, guild, policy = _start(
            store, db, account_id, generation, character_id, expected_guild_id
        )
        definition = _definition(policy, guild, compartment_id)
        for action in ("view", "deposit" if deposit else "withdraw"):
            _permission(db, guild, character_id, definition, action)
        chest = _chest(db, guild, compartment_id, definition)
        replay = _receipt(db, character_id, operation_key, guild, request)
        character = _character(db, account_id, character_id)
        if replay:
            return dict(character=character, chest=chest, applied=False)
        _requests(requests, chest, deposit)
        _revision(chest, expected_revision)
        inventory = [
            custody._snapshot(db, item) for item in character["inventory_items"]
        ]
        selected = {row["uid"] for row in requests}
        if deposit:
            if selected & custody._equipped(character):
                raise ValueError("Unequip the guild chest item from every build first")
            for entry in inventory:
                if entry["item"]["uid"] in selected:
                    supplied = next(
                        row for row in requests if row["uid"] == entry["item"]["uid"]
                    )
                    if (
                        supplied.get("reference", entry["item"]["reference"])
                        != entry["item"]["reference"]
                    ):
                        raise ValueError(
                            "Guild chest deposit reference does not match owned item"
                        )
                    _eligible(entry)
        else:
            for entry in chest["items"]:
                if entry["item"]["uid"] in selected:
                    _eligible(entry)
        from wakfu_server.inventory_move import STACKS
        from wakfu_server.inventory_uids import allocate

        planned, updated = custody.plan(
            inventory,
            chest,
            requests,
            deposit=deposit,
            character_id=character_id,
            containers=character["inventory_containers"],
            rules=STACKS,
            allocate=lambda: allocate(db),
        )
        custody.persist_inventory(db, character_id, inventory, planned)
        _save(db, updated)
        _finish(db, character_id, operation_key, guild, request)
        service._event(
            db,
            guild["id"],
            "chest_transfer",
            dict(
                character_id=character_id,
                compartment_id=compartment_id,
                deposit=deposit,
                revision=updated["revision"],
            ),
        )
        return dict(
            character=_character(db, account_id, character_id),
            chest=updated,
            applied=True,
        )


def plan_move(source, source_slot, destination, destination_slot):
    """Swap cells without cloning items or changing quantities/metadata."""
    if source["guild_id"] != destination["guild_id"]:
        raise ValueError("Foreign guild chest move destination")
    _validate_chest(source)
    _validate_chest(destination)
    if source["id"] != destination["id"] and (
        {entry["item"]["uid"] for entry in source["items"]}
        & {entry["item"]["uid"] for entry in destination["items"]}
    ):
        raise ValueError("Duplicate guild chest item identity")
    source, destination = deepcopy(source), deepcopy(destination)
    same = source["id"] == destination["id"]
    if same:
        destination = source
    for chest, slot in ((source, source_slot), (destination, destination_slot)):
        _integer(slot, "move slot", 0, chest["capacity"] - 1)
        if len({entry["slot"] for entry in chest["items"]}) != len(chest["items"]):
            raise ValueError("Duplicate guild chest slot")
    moved = next(
        (entry for entry in source["items"] if entry["slot"] == source_slot), None
    )
    if moved is None:
        raise ValueError("Guild chest move source is empty")
    if same and source_slot == destination_slot:
        raise ValueError("Guild chest move has identical cells")
    other = next(
        (entry for entry in destination["items"] if entry["slot"] == destination_slot),
        None,
    )
    source["items"].remove(moved)
    if other is not None:
        destination["items"].remove(other)
        other["slot"] = source_slot
        source["items"].append(other)
    moved["slot"] = destination_slot
    destination["items"].append(moved)
    return source, destination


def move(
    store,
    account_id,
    generation,
    character_id,
    source_compartment_id,
    source_slot,
    destination_compartment_id,
    destination_slot,
    *,
    operation_key,
    expected_revisions,
    expected_guild_id=None
):
    request = dict(
        operation="move",
        source_compartment_id=source_compartment_id,
        source_slot=source_slot,
        destination_compartment_id=destination_compartment_id,
        destination_slot=destination_slot,
        expected_revisions={
            str(key): value for key, value in expected_revisions.items()
        },
    )
    with store.connection() as db:
        service, guild, policy = _start(
            store, db, account_id, generation, character_id, expected_guild_id
        )
        chests = {}
        for identity in sorted({source_compartment_id, destination_compartment_id}):
            definition = _definition(policy, guild, identity)
            for action in ("view", "move", "withdraw", "deposit"):
                _permission(db, guild, character_id, definition, action)
            chests[identity] = _chest(db, guild, identity, definition)
        if _receipt(db, character_id, operation_key, guild, request):
            return dict(chests=list(chests.values()), applied=False)
        for identity, chest in chests.items():
            _revision(chest, expected_revisions.get(identity))
        source, destination = plan_move(
            chests[source_compartment_id],
            source_slot,
            chests[destination_compartment_id],
            destination_slot,
        )
        updated = {source["id"]: source, destination["id"]: destination}
        for chest in updated.values():
            _save(db, chest)
        _finish(db, character_id, operation_key, guild, request)
        service._event(
            db,
            guild["id"],
            "chest_move",
            dict(character_id=character_id, compartments=sorted(updated)),
        )
        return dict(chests=list(updated.values()), applied=True)
