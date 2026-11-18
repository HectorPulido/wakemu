"""Explicit, pinned scoring parameters for reconstructed order trials.

The shipped recipe matrix is an authored approximation, not recovered server
code. Keeping it outside the reducer permits calibration without changing
native action execution, score custody or reward settlement.
"""
from hashlib import sha256
import json
from pathlib import Path

SCORING_SHA256 = "65f46e43b50894f394704e13e098687c7f39c7c16003a7c381000cc9442eb025"
_SOURCE = (
    Path(__file__).parents[1]
    / "achievements/order_trial_profiles/astrub_pizzlarva.scoring.json"
)


def validate(document):
    from wakfu_server.achievements.native_order_trials import OrderRules

    if (
        type(document) is not dict
        or set(document)
        != {
            "schema",
            "id",
            "provenance",
            "score_threshold",
            "strike_limit",
            "ingredient_batch",
            "ingredient_capacity",
            "weights",
            "rationale",
            "evidence_urls",
            "native_accuracy",
        }
        or document["schema"] != "reviewed-order-trial-scoring-v1"
        or type(document["id"]) is not str
        or not document["id"]
        or type(document["provenance"]) is not dict
        or set(document["provenance"]) != {"kind", "evidence"}
        or document["provenance"]["kind"] != "reviewed_reconstruction"
        or not all(
            type(document[k]) is str and document[k].strip()
            for k in ("rationale", "native_accuracy")
        )
        or type(document["provenance"]["evidence"]) is not str
        or not document["provenance"]["evidence"].strip()
        or type(document["evidence_urls"]) is not list
        or not document["evidence_urls"]
        or any(
            type(url) is not str or not url.startswith("https://")
            for url in document["evidence_urls"]
        )
        or type(document["weights"]) is not list
        or any(
            type(row) is not list
            or len(row) != 3
            or type(row[0]) is not str
            or type(row[1]) is not str
            for row in document["weights"]
        )
    ):
        raise ValueError("Order scoring requires explicit reconstruction provenance")
    return OrderRules(
        tuple(
            ((color, ingredient), points)
            for color, ingredient, points in document["weights"]
        ),
        score_threshold=document["score_threshold"],
        strike_limit=document["strike_limit"],
        ingredient_batch=document["ingredient_batch"],
        ingredient_capacity=document["ingredient_capacity"],
    )


def load():
    """Return the pinned rules and their honest, durable provenance."""
    raw = _SOURCE.read_bytes()
    if sha256(raw).hexdigest() != SCORING_SHA256:
        raise ValueError(
            "Order scoring parameters changed without a reviewed source pin"
        )
    document = json.loads(raw)
    return validate(document), document["provenance"]
