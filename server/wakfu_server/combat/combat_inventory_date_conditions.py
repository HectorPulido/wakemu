"""Native eJL UTC calendar and eKE quantities over an owned ordinary inventory.

eJL(day,month,year,hour,minute,second) constructs TP in UTC milliseconds.
The restricted calendar supports valid post-cutover Gregorian dates only;
lenient overflow and historical cutover dates remain explicit unknowns.
eKE narrows each requested reference to int and adds quantities per occurrence.
The ordinary inventory source is complete for this server's owned containers;
missing snapshots must never be treated as empty.
"""
from datetime import datetime, timedelta, timezone


def calendar_milliseconds(values):
    if len(values) != 6 or any(type(v) is not int for v in values):
        raise ValueError("Native GetDate requires six constant integers")
    day, month, year, hour, minute, second = [
        ((v + 2**31) % 2**32) - 2**31 for v in values
    ]
    if not 1583 <= year <= 9999:
        raise ValueError(
            "Native GetDate historical/overflow calendar remains unsupported"
        )
    date = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    return (date - datetime(1970, 1, 1, tzinfo=timezone.utc)) // timedelta(
        milliseconds=1
    )


def owned_item_quantity(items, references):
    if not isinstance(items, (list, tuple)):
        raise ValueError("Native GetItemQuantity lacks complete owned inventory")
    counts = {}
    identities = set()
    for item in items:
        if (
            not isinstance(item, dict)
            or type(item.get("uid")) is not int
            or item["uid"] in identities
            or type(item.get("reference")) is not int
            or type(item.get("quantity")) is not int
            or item["quantity"] <= 0
        ):
            raise ValueError("Invalid owned inventory quantity authority")
        identities.add(item["uid"])
        counts[item["reference"]] = counts.get(item["reference"], 0) + item["quantity"]
    total = 0
    for reference in references:
        if type(reference) is not int or not -(2**63) <= reference < 2**63:
            raise ValueError("Native item reference requires signed long")
        narrowed = ((reference + 2**31) % 2**32) - 2**31
        total = ((total + counts.get(narrowed, 0) + 2**31) % 2**32) - 2**31
    return total
