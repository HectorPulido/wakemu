"""Diagnostic phase attribution; this never changes qualification decisions."""


def initialization_diagnostic(
    reference, raw_triples, minimum, maximum, cases, *, proven
):
    required = set(range(minimum, maximum + 1)) if raw_triples else set()
    verified = set()
    failed = set()
    attempted = set()
    for case in cases:
        level = case["level"]
        receipts = case.get("initialization_receipts", ())
        if receipts:
            attempted.add(level)
        if any(proven(reference, level, raw_triples, r) for r in receipts):
            verified.add(level)
        if any(
            str(error).startswith("initialization:") for error in case.get("errors", ())
        ):
            attempted.add(level)
            failed.add(level)
    missing = required - verified
    # Missing descriptors remain pending; unvisited descriptors are not failures.
    return dict(
        pending=bool(missing),
        failed_levels=sorted(failed),
        unproven_attempted_levels=sorted((attempted & required) - verified),
        unvisited_levels=sorted(required - attempted),
        reason=(
            "native_initial_states_not_initialized"
            if failed
            else "native_initial_state_coverage_incomplete"
        )
        if missing
        else None,
    )


def native_case_coverage(minimum, maximum, spell_ids, cases):
    """Diagnostic counts only; missing cases never count as attempted or passed."""
    expected = {
        (level, spell) for level in range(minimum, maximum + 1) for spell in spell_ids
    }
    observed = [(case.get("level"), case.get("spell_id")) for case in cases]
    unique = set(observed)
    valid = unique & expected
    return dict(
        expected_native_level_count=maximum - minimum + 1,
        expected_owned_spell_count=len(set(spell_ids)),
        expected_native_case_count=len(expected),
        observed_native_case_count=len(observed),
        observed_unique_native_case_count=len(unique),
        visited_native_case_count=len(valid),
        unvisited_native_case_count=len(expected - valid),
        visited_native_levels=sorted({level for level, spell in valid}),
        unvisited_native_levels=sorted(
            set(range(minimum, maximum + 1)) - {level for level, spell in valid}
        ),
        duplicate_case_count=len(observed) - len(unique),
        foreign_case_count=len(unique - expected),
        full_native_case_coverage=(
            len(observed) == len(expected) and unique == expected
        ),
    )
