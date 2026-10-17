"""Independent owned state/area lifecycle model at native logical callbacks."""
import hashlib
import json
from itertools import islice

from .combat_protocol_reconstruction import Recipient, decode_packet


def verify_native_area_lifecycle(
    *, packets, actor_ids, recipient, projection, proof_bytes, trusted_proof_sha256
):
    """Compare a declared UID lifecycle slice, not an unsupported full stream.

    Each area becomes a real permitted PV/state owner when registered, and its
    owned states leave the active projection when Qs unregisters that area.
    Native callback facts are pinned per exact frame, never fabricated fences.
    """
    base = dict(
        qualified=False,
        rendering_qualified=False,
        visual_script_qualified=False,
        live_delivery_qualified=False,
        scope="selected UID native logical lifecycle callbacks",
        reasons=[],
    )
    try:
        if (
            not isinstance(recipient, Recipient)
            or type(proof_bytes) is not bytes
            or len(proof_bytes) > 4 * 1024 * 1024
            or not isinstance(projection, dict)
            or set(projection) != {"states", "areas"}
        ):
            raise ValueError(
                "Explicit recipient, states/areas projection and bounded proof required"
            )
        proof_hash = hashlib.sha256(proof_bytes).hexdigest()
        if not trusted_proof_sha256 or trusted_proof_sha256 != proof_hash:
            raise ValueError("Native area proof is not independently pinned")
        proof = json.loads(proof_bytes)
        if (
            proof.get("schema") != "wakemu-pilot-area-native-proof-v1"
            or proof.get("complete") is not True
            or proof.get("source_stable") is not True
            or type(proof.get("compile_returncode")) is not int
            or proof["compile_returncode"] != 0
            or proof.get("instrumentation") != "none"
            or "client/lib/wakfu-client.jar" not in proof.get("classpath", {})
            or not proof.get("bdata")
            or "sniffer/java/VerifyPilotAreaQueue.java" not in proof.get("source", {})
        ):
            raise ValueError(
                "Native retained lifecycle proof incomplete or wrong consumer"
            )
        packets = tuple(islice(iter(packets), 4097))
        if not 1 <= len(packets) <= 4096:
            raise ValueError("Bounded actual lifecycle slice required")
        hashes = [hashlib.sha256(body).hexdigest() for _, body in packets]
        record = next(
            (
                row
                for row in proof.get("cases", ())
                if row.get("packets_sha256") == hashes
            ),
            None,
        )
        if record is None or record.get("complete") is not True:
            raise ValueError("Exact ordered lifecycle bytes absent from native proof")
        native = record["native"]
        stages = native["stages"]
        if native.get("completed_normally") is not True or len(stages) != len(packets):
            raise ValueError("Native lifecycle callback observations incomplete")
        actors = set(actor_ids)
        if not all(type(actor) is int and actor != 0 for actor in actors):
            raise ValueError("Explicit native actor registrations required")
        states, areas, runners = {}, {}, {}
        fight = None
        actions = []
        for packet, observation in zip(packets, stages):
            decoded = decode_packet(*packet)
            if decoded["kind"] not in ("effect", "effect_remove"):
                raise ValueError("Unsupported frame in retained lifecycle slice")
            if fight is None:
                fight = decoded["fight"]
            if fight != decoded["fight"]:
                raise ValueError("Lifecycle fight identities differ")
            effect = decoded["effect"]
            family, uid = effect["family"], effect["uid"]
            if family not in (308, 310, 315) or uid <= 0:
                raise ValueError("Unsupported native retained family/identity")
            if (
                observation.get("opcode") != packet[0]
                or observation.get("family") != family
                or observation.get("action_id") != decoded["action"]
                or observation.get("uid") != uid
                or observation.get("generic_effect") != effect["definition"]
                or observation.get("native_completed_action_ids") != [decoded["action"]]
                or observation.get("queue_drained") is not True
            ):
                raise ValueError(
                    "Native lifecycle opcode/runner/action/completion differs"
                )
            if observation["before"] != dict(states=states, areas=areas):
                raise ValueError("Byte model differs before original callback")
            known = actors | set(map(int, areas))
            if any(
                effect[key] is not None and effect[key] not in known
                for key in ("caster", "target")
            ):
                raise ValueError(
                    "Native lifecycle owner references unregistered actor or area PV"
                )
            if (
                effect["container_type"] == 3
                and str(effect["container_id"]) not in areas
            ):
                raise ValueError(
                    "Native lifecycle source area container is unregistered"
                )
            if decoded["kind"] == "effect_remove":
                existing = runners.get(uid)
                if existing is None or any(
                    existing[key] != effect[key]
                    for key in (
                        "family",
                        "definition",
                        "base_uid",
                        "caster",
                        "target",
                        "container_type",
                        "container_id",
                    )
                ):
                    raise ValueError(
                        "Retirement references unknown or changed owned native runner"
                    )
                owner = (
                    effect["target"]
                    if effect["target"] is not None
                    else effect["caster"]
                )
                if decoded["removal_target"] != owner:
                    raise ValueError("Retirement owner-manager identity differs")
                runners.pop(uid)
                if family == 310:
                    states.pop(str(uid), None)
                elif not existing["keep_after"]:
                    area = str(existing["area_uid"])
                    areas.pop(area, None)
                    states = {
                        key: value
                        for key, value in states.items()
                        if value["owner"] != int(area)
                    }
            elif family == 310:
                if observation.get("retained") is True:
                    if uid in runners:
                        raise ValueError("Duplicate active state identity")
                    owner = (
                        effect["target"]
                        if effect["target"] is not None
                        else effect["caster"]
                    )
                    states[str(uid)] = dict(
                        state_id=effect["state_id"], level=effect["level"], owner=owner
                    )
                    runners[uid] = effect
            else:
                area = str(effect["area_uid"])
                if area in areas or uid in runners or "cell" not in effect:
                    raise ValueError("Duplicate or unlocated native area registration")
                areas[area] = dict(
                    prototype=effect["prototype"], cell=list(effect["cell"])
                )
                if observation.get("retained") is True:
                    runners[uid] = effect
            if observation["after"] != dict(states=states, areas=areas):
                raise ValueError(
                    "Independent byte model differs from original native callback"
                )
            actions.append(decoded["action"])
        view = dict(states=states, areas=areas)
        matches = view == projection
        return dict(
            base,
            qualified=matches,
            native_case=record["id"],
            native_proof_sha256=proof_hash,
            recipient=dict(role=recipient.role, generation=recipient.generation),
            executed=view,
            action_ids=actions,
            pending=False,
            reasons=[] if matches else ["permitted_lifecycle_projection_differs"],
        )
    except (ValueError, KeyError, TypeError, IndexError, OverflowError) as error:
        return dict(base, reasons=[str(error)])
