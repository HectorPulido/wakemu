"""Source-only alternate NPC owners for resource-rejected spell contexts.

Base resource affordance is a scheduling hint, never execution qualification.
Native spell levels are retained verbatim; unresolved bounds stay unresolved.
"""


def plan_alternate_resource_owners(pending, monsters, profiles, casting, producer_rows):
    by_spell = {}
    for row in pending:
        by_spell.setdefault(row["spell_id"], set()).add(row["reference"])
    plans = []
    unresolved = []
    for spell, failed_owners in sorted(by_spell.items()):
        choices = []
        for ref, monster in sorted(monsters.items()):
            owned = [a for a in monster["native_abilities"] if a["spell_id"] == spell]
            if not owned or ref in failed_owners:
                continue
            if len(owned) != 1:
                raise ValueError("Ambiguous actual native owned ability")
            edges = producer_rows.get(ref, {}).get("producers", [])
            npc = [e for e in edges if e.get("source_kind") == "npc"]
            classes = [e for e in edges if e.get("source_kind") == "class"]
            if classes and not npc:
                unresolved.append(
                    dict(
                        reference=ref,
                        spell_id=spell,
                        reason="class_only_creator_separate_scope",
                    )
                )
                continue
            level = monster["min_level"]
            profile = profiles.get(str(ref))
            pl = owned[0]["level_parameter"]
            pl = level if pl == -1 else pl
            table = casting.get(str(spell), {})
            costs = table.get("costs")
            if (
                not isinstance(profile, dict)
                or profile.get("base_level") != level
                or type(pl) is not int
                or pl <= 0
                or not isinstance(costs, list)
                or pl > len(costs)
            ):
                unresolved.append(
                    dict(
                        reference=ref,
                        spell_id=spell,
                        spell_level=pl,
                        reason="unknown_exact_native_resource_or_level_bounds",
                    )
                )
                continue
            cost = costs[pl - 1]
            if len(cost) != 3 or any(type(v) is not int or v < 0 for v in cost):
                raise ValueError("Invalid source native spell cost operands")
            available = {}
            for stat in (2, 3, 4):
                value = profile["at_base_level"].get(str(stat), {}).get("current")
                if type(value) is not int:
                    raise ValueError("Missing exact native base resource")
                available[str(stat)] = value
            deficits = {
                str(stat): max(0, required - available[str(stat)])
                for stat, required in zip((2, 3, 4), cost)
            }
            affordable = not any(deficits.values())
            choices.append(
                dict(
                    reference=ref,
                    actor_level=level,
                    spell_id=spell,
                    spell_level=pl,
                    source_available=available,
                    source_cost=dict(zip(("2", "3", "4"), cost)),
                    source_deficits=deficits,
                    source_base_affordable=affordable,
                    genuine_npc_creator_routes=npc,
                    class_routes_preserved_separately=classes,
                    requires_actual_constructor_if_resource_context_needed=bool(
                        npc and not affordable
                    ),
                    actual_available_proven=False,
                    qualification=False,
                )
            )
        choices.sort(
            key=lambda r: (
                not r["source_base_affordable"],
                not bool(r["genuine_npc_creator_routes"]),
                sum(r["source_deficits"].values()),
                r["actor_level"],
                r["reference"],
            )
        )
        eligible = [r for r in choices if r["source_base_affordable"]]
        plans.append(
            dict(
                spell_id=spell,
                failed_owner_refs=sorted(failed_owners),
                selected_context=eligible[0] if eligible else None,
                ranked_authentic_contexts=choices,
            )
        )
    return dict(
        schema="native-resource-alternate-owner-plan-v1",
        spells=plans,
        unresolved_source_contexts=unresolved,
        new_execution=False,
        admission=False,
    )
