"""Atomic native random-box consumption with stable, private server draws.

Native brq proves displayed relative weights and guaranteed negative entries.
The type1 server policy selects one weighted branch plus every guaranteed branch;
quantity N on a nested table makes N independent draws. This policy is explicit
because the installed client does not contain the original server draw engine.
"""
import hashlib
import hmac
import math
import struct
from fractions import Fraction

from wakfu_server.inventory_owner import lock_item_owner

SOURCE_SHA256 = "1ee0fa5fc731932c084570d5f653a26cdacd964d5424270bb38c398d48dc1b97"
EXTENSION_SHA256 = "6a7fce42ddcf88910a319bcd2d35a3a377c228676a12e144080baeeadb368264"
ALGORITHM = b"native-box-weighted-v1"


class PrivateDraw:
    """Uniform deterministic stream; rollbacks retain the same committed nonce."""

    def __init__(self, secret, account_id, action_id, source_uid, nonce):
        if not isinstance(secret, bytes) or len(secret) != 32:
            raise ValueError("Missing private item-draw entropy")
        if any(
            type(value) is not int or not 0 <= value < 2**63
            for value in (account_id, action_id, source_uid, nonce)
        ):
            raise ValueError("Invalid private item-draw identity")
        self._seed = hmac.digest(
            secret,
            ALGORITHM + struct.pack(">qqqq", account_id, action_id, source_uid, nonce),
            "sha256",
        )
        self._counter = 0

    def randbelow(self, upper):
        if type(upper) is not int or upper <= 0:
            raise ValueError("Invalid random item draw bound")
        if upper == 1:
            return 0
        width = (upper.bit_length() + 7) // 8
        mask = (1 << upper.bit_length()) - 1
        while True:
            data = bytearray()
            while len(data) < width:
                data.extend(
                    hmac.digest(self._seed, struct.pack(">Q", self._counter), "sha256")
                )
                self._counter += 1
            value = int.from_bytes(data[:width], "big") & mask
            if value < upper:
                return value


def action_class(body):
    from wakfu_server.simple_item_actions import _action_classes

    if not isinstance(body, bytes) or len(body) < 12:
        raise ValueError("Invalid native random item request")
    action_id, source_uid = struct.unpack_from(">iq", body)
    if action_id <= 0 or source_uid <= 0:
        raise ValueError("Invalid native random item identity")
    classes = _action_classes().get(action_id, set())
    if "bHJ" not in classes:
        return None
    if classes != {"bHJ"} or len(body) != 12:
        raise ValueError("Invalid native random item grammar")
    return "bHJ"


def _integer(value, minimum, maximum, label):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"Invalid native random {label}")
    return value


def draw_products(
    root_table, table_lookup, rng, *, allowed_table_types=(1,), entry_allowed=None
):
    """Resolve qualified native tables without flattening or changing their weights."""
    products = {}
    visited = 0

    def quantity(entry):
        lower = _integer(entry["cqy"], 0, 32767, "minimum quantity")
        upper = _integer(entry["cqz"], lower, 32767, "maximum quantity")
        return lower + rng.randbelow(upper - lower + 1)

    def grant(entry, path):
        amount = quantity(entry)
        if amount == 0:
            return
        reference = _integer(entry["aAi"], 0, 2**31 - 1, "entry reference")
        if type(entry["cqA"]) is not bool:
            raise ValueError("Invalid native random nested-table flag")
        if entry["cqA"]:
            if reference == 0:
                raise ValueError("Invalid native nested table reference")
            for _ in range(amount):
                visit(reference, path)
        elif reference != 0:
            products[reference] = products.get(reference, 0) + amount
            if products[reference] >= 2**31:
                raise ValueError("Native random product quantity exceeds storage")

    def visit(reference, path):
        nonlocal visited
        visited += 1
        if reference in path or len(path) >= 64 or visited > 100000:
            raise ValueError("Invalid native random table recursion")
        table = table_lookup(reference)
        if table.get("d") != reference or table.get("czg") not in allowed_table_types:
            raise ValueError("Unsupported native random table kind")
        entries = table.get("gBN")
        if not isinstance(entries, list):
            raise ValueError("Invalid native random table entries")
        guaranteed, weighted = [], []
        for entry in entries:
            weight = entry.get("cmY")
            if type(weight) not in (int, float) or not math.isfinite(weight):
                raise ValueError("Invalid native random weight")
            if weight == 0:
                continue
            if (entry.get("bfh"), entry.get("czl"), entry.get("csE")) != (1, 0, 1):
                raise ValueError("Unsupported native random roll configuration")
            if entry.get("gBO"):
                raise ValueError("Unsupported native random entry conditions")
            if entry.get("czk"):
                if entry_allowed is None:
                    raise ValueError("Unsupported native random entry criterion")
                accepted = entry_allowed(entry["czk"])
                if type(accepted) is not bool:
                    raise ValueError("Invalid native random entry criterion result")
                if not accepted:
                    continue
            if weight == -1:
                guaranteed.append(entry)
            elif weight < 0:
                raise ValueError("Unsupported native random guaranteed weight")
            else:
                weighted.append((entry, Fraction(str(weight))))
        selected = []
        if weighted:
            denominator = math.lcm(*(value.denominator for _, value in weighted))
            weights = [
                value.numerator * (denominator // value.denominator)
                for _, value in weighted
            ]
            roll = rng.randbelow(sum(weights))
            for (entry, _), weight in zip(weighted, weights):
                if roll < weight:
                    selected.append(entry)
                    break
                roll -= weight
        for entry in guaranteed + selected:
            grant(entry, path + (reference,))

    visit(_integer(root_table, 1, 2**31 - 1, "root table"), ())
    return products


def blind_box_packets(parameters, products):
    """Original cxe13817 stops the optional native blind-box rolling dialog."""
    if not isinstance(parameters, list) or len(parameters) not in (1, 2):
        raise ValueError("Invalid native random box presentation parameters")
    visible = len(parameters) == 1 or parameters[1].lower() == "true"
    if not visible:
        return []
    # All 94 qualified visible native lists are flat, positive-only and have
    # exactly one real item outcome. Multi-product tables disable this dialog.
    if len(products) != 1:
        raise ValueError("Invalid native visible random box outcome")
    reference = next(iter(products))
    return [(13817, struct.pack(">i", reference))]


def use(
    store, account_id, generation, character_id, body, *, in_fight, native_map_id=None
):
    """Consume one owned box and publish results only after the transaction commits."""
    if type(in_fight) is not bool or in_fight:
        raise ValueError("Sal del combate para utilizar este objeto")
    if action_class(body) != "bHJ":
        raise ValueError("Unsupported native random item action")
    action_id, source_uid = struct.unpack(">iq", body)
    from wakfu_server.simple_item_actions import _criterion, _equipped, _idle

    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        owner_id = lock_item_owner(
            store, db, account_id, generation, character_id, (source_uid,)
        )
        _idle(db, owner_id, store.now())
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (source_uid, owner_id),
        ).fetchone()
        if item is None:
            raise ValueError("El objeto ya no está disponible")
        rule = db.execute(
            "SELECT * FROM native_random_item_actions WHERE item_ref=%s",
            (item["reference"],),
        ).fetchone()
        if (
            rule is None
            or rule["action_id"] != action_id
            or rule["source_sha256"] != SOURCE_SHA256
        ):
            raise ValueError("El objeto no corresponde a esta acción")
        from wakfu_server.haven_bag_furniture_knowledge import _rules

        published = _rules().get(item["reference"], {})
        if (
            published.get("use_action_id") != action_id
            or published.get("use_action_class") != "bHJ"
        ):
            raise ValueError("La acción no coincide con el catálogo activo")
        if not rule["available"]:
            raise ValueError(
                "Esta caja necesita datos nativos que aún no están disponibles"
            )
        character = store.character(account_id, owner_id, db)
        if _equipped(character, source_uid):
            raise ValueError("Desequipa el objeto antes de utilizarlo")
        if not _criterion(
            store, db, account_id, character, rule["use_criterion"], native_map_id
        ):
            raise ValueError("No cumples las condiciones de uso de este objeto")
        if not _criterion(
            store, db, account_id, character, rule["criterion"], native_map_id
        ):
            raise ValueError("No cumples las condiciones de este objeto")
        db.execute(
            "INSERT INTO random_item_use_counters(source_uid) VALUES(%s) ON CONFLICT DO NOTHING",
            (source_uid,),
        )
        nonce = db.execute(
            "SELECT next_use FROM random_item_use_counters WHERE source_uid=%s FOR UPDATE",
            (source_uid,),
        ).fetchone()["next_use"]
        _integer(nonce, 0, 2**63 - 2, "use counter")
        entropy = db.execute(
            "SELECT secret FROM random_item_entropy WHERE singleton=true"
        ).fetchone()
        if entropy is None:
            raise ValueError("Missing private item-draw entropy")
        rng = PrivateDraw(
            bytes(entropy["secret"]), account_id, action_id, source_uid, nonce
        )
        tables = {}

        def lookup(reference):
            if reference not in tables:
                row = db.execute(
                    "SELECT payload,source_sha256 FROM native_random_item_tables WHERE reference=%s",
                    (reference,),
                ).fetchone()
                if row is None or row["source_sha256"] != SOURCE_SHA256:
                    raise ValueError("Missing qualified native random table")
                tables[reference] = row["payload"]
            return tables[reference]

        extension = db.execute(
            "SELECT policy,source_sha256 FROM native_random_item_extensions WHERE item_ref=%s",
            (item["reference"],),
        ).fetchone()
        options = {}
        if extension is not None:
            policy = extension["policy"]
            if (
                extension["source_sha256"] != EXTENSION_SHA256
                or not isinstance(policy, dict)
                or policy.get("kind") != "native-display-relative-weighted-types1-3-v1"
                or policy.get("base_source_sha256") != SOURCE_SHA256
                or policy.get("table_types") != [1, 3]
                or not isinstance(policy.get("criteria"), list)
            ):
                raise ValueError("Invalid native random extension policy")
            mode = db.execute(
                "SELECT value FROM settings WHERE name='dungeon_server_mode'"
            ).fetchone()
            value = None if mode is None else mode["value"]
            if (
                not isinstance(value, dict)
                or value.get("version") != 1
                or type(value.get("is_neo_server")) is not bool
            ):
                raise ValueError("Native random server mode is not configured")
            from wakfu_server.random_item_criteria import evaluate

            def allowed(text):
                if text not in policy["criteria"]:
                    raise ValueError("Unqualified native random entry criterion")
                return evaluate(
                    text,
                    character,
                    native_map_id=character["map_id"]
                    if native_map_id is None
                    else native_map_id,
                    is_neo_server=value["is_neo_server"],
                )

            options = dict(allowed_table_types=(1, 3), entry_allowed=allowed)
        products = draw_products(rule["root_table"], lookup, rng, **options)
        presentation_packets = blind_box_packets(rule["action_parameters"], products)
        db.execute(
            "UPDATE random_item_use_counters SET next_use=next_use+1 WHERE source_uid=%s",
            (source_uid,),
        )
        if item["quantity"] == 1:
            db.execute(
                "DELETE FROM inventory_items WHERE uid=%s AND character_id=%s",
                (source_uid, owner_id),
            )
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s AND character_id=%s",
                (source_uid, owner_id),
            )
        packets = [(12470, struct.pack(">qh", source_uid, -1))]
        if products:
            from wakfu_server.item_action_delivery import grant_outputs

            result = grant_outputs(
                store, db, account_id, generation, character, products
            )
            packets.extend(result["packets"])
            character = result["character"]
        else:
            character = store.character(account_id, owner_id, db)
        packets.extend(presentation_packets)
        return dict(
            character=character,
            packets=packets,
            applied=True,
            native_class="bHJ",
            consumed=1,
        )
