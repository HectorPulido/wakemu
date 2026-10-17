"""Native subscription family metadata without runtime or catalog imports."""

GROUP_SUBSCRIPTION_FAMILIES = (
    330,
    341,
    345,
    349,
    352,
    844,
    865,
    910,
    912,
    913,
    949,
    999,
    1020,
    1041,
    1047,
    1076,
    1080,
    1103,
    1100,
    1101,
)
DEFERRED_RUNNERS = {
    1: "eXt",  # Fresh damage C()/resources wait for the subscribed event.
    25: "eXs",  # Fresh inherited eZR wire; healing waits for its event.
    28: "eXc",  # Fresh inherited eZR wire; HP assignment waits for its event.
    304: "eWu",
    309: "eZc",  # Empty C()/inherited eZR wire; reflection waits for its event.
    314: "eYQ",
    321: "eZi",
    400: "eXE",
    401: "eZh",
    421: "eXe",
    982: "eXW",  # Inherited eXY.C is a no-op; cleanup waits for activation.
    430: "eZL",
    877: "eWV",  # Fresh inherited eZR; minimum changes only on activation.
    1003: "eWV",
    1001: "eWZ",
    1093: "eZJ",
}
SUBSCRIPTION_FAMILIES = GROUP_SUBSCRIPTION_FAMILIES + tuple(DEFERRED_RUNNERS)
