"""Reconcile compact committed casting selections with exact frozen criteria."""


def reconcile(rows, matrix):
    index = {(row["spell"], row["branch"]): row for row in matrix["rows"]}
    unique, matched, rejected = [], [], []
    for row in rows:
        selection = row.get("native_casting_selection") or {}
        if (
            row.get("commit_status") != "committed"
            or row.get("source_preserved") is not True
        ):
            rejected.append(
                dict(reason="not source-preserved actual commit", observation=row)
            )
            continue
        if selection.get("reference") != row.get("reference"):
            rejected.append(dict(reason="reference identity mismatch", observation=row))
            continue
        unknown = set(selection.get("unknown_equivalent_rule_indices", []))
        for rule in selection.get("matched_rules", []):
            key = (row["reference"], rule["index"])
            contract = index.get(key)
            if contract is None or contract["criterion_raw"] != rule.get("criteria"):
                rejected.append(
                    dict(
                        reason="exact frozen branch/criterion identity missing",
                        observation=row,
                        rule=rule,
                    )
                )
                continue
            if rule["index"] in unknown:
                rejected.append(
                    dict(
                        reason="unknown-equivalent rule is not positive evidence",
                        observation=row,
                        rule=rule,
                    )
                )
                continue
            observation = dict(
                spell=key[0],
                branch=key[1],
                evaluation_level=selection["evaluation_level"],
                table_index=selection["table_index"],
                criterion_raw=rule["criteria"],
                selected_values=selection["selected_values"],
                baseline_values=selection["baseline_values"],
                costs=row.get("costs"),
                native_casting_flags=row.get("native_casting_flags"),
                report_sha256=row.get("report_sha256"),
                source_contract_sha256=row.get("source_contract_sha256"),
                proof="unique conditional selection and committed cast"
                if selection.get("unique_matching_rule") is True
                and len(selection["matched_rules"]) == 1
                and not unknown
                else "known criterion matched in equivalent multi/unknown table; no unique selection",
                removal_or_producer_semantics_verified=False,
            )
            (unique if observation["proof"].startswith("unique") else matched).append(
                observation
            )
    return dict(
        unique_selected_committed=unique,
        known_matched_committed=matched,
        rejected=rejected,
    )
