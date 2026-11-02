"""Read current, explicitly eligible purchase prices without changing shop visibility."""


def _validate_references(references):
    if (
        not isinstance(references, list)
        or not 1 <= len(references) <= 128
        or any(type(reference) is not int or reference <= 0 for reference in references)
        or len(set(references)) != len(references)
    ):
        raise ValueError("Invalid buyer price references")


def purchase_prices(store, references):
    _validate_references(references)
    with store.connection() as db:
        db.execute("SET TRANSACTION READ ONLY")
        return purchase_prices_in_transaction(db, references)


def purchase_prices_in_transaction(db, references):
    """Share the same eligibility authority with owned quote rejection."""
    _validate_references(references)
    from wakfu_server.exchange_rules import eligibility

    rows = db.execute(
        "SELECT a.item_ref,a.quantity,a.price_kamas FROM shop_articles a "
        "JOIN shop_categories c ON c.key=a.category "
        "WHERE a.item_ref=ANY(%s) AND "
        "(a.buyer_enabled OR (a.enabled AND c.enabled)) ORDER BY a.id",
        (references,),
    ).fetchall()
    prices = []
    for row in rows:
        try:
            allowed = eligibility(row["item_ref"])
        except ValueError:
            allowed = False
        if allowed:
            prices.append(
                dict(
                    reference=row["item_ref"],
                    quantity=row["quantity"],
                    price_kamas=row["price_kamas"],
                )
            )
    return {"prices": prices}
