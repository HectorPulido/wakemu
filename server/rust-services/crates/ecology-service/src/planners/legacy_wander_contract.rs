//! Legacy wander planner assertions exercised against the actual native kernels.
use super::*;
use rand::{rngs::StdRng, SeedableRng};

fn actor(id: i64, p: Point) -> Value {
    json!({"id":id,"ref":5525,"x":p[0],"y":p[1],"z":p[2],"level":1})
}
fn graph(edges: &[(Point, Point)]) -> Geometry {
    let cells: BTreeSet<_> = edges.iter().flat_map(|(a, b)| [*a, *b]).collect();
    geometry(&json!({"cells":cells,"edges":edges})).unwrap()
}
fn run(
    roster: &[Value],
    players: &[Point],
    edges: &[(Point, Point)],
    blocked: &[Point],
    allowed: impl Fn(Point) -> bool,
) -> Option<MovePlan> {
    group_path(
        roster,
        players,
        &[],
        &graph(edges),
        &blocked.iter().copied().collect(),
        20,
        1,
        1,
        &allowed,
        &mut StdRng::seed_from_u64(10),
    )
    .unwrap()
}
#[test]
fn player_absence_distance_and_exact_chebyshev_boundary() {
    let a = [0, 0, 0];
    let b = [1, 0, 1];
    let roster = [actor(-1, a)];
    let indexed = graph(&[(a, b)]);
    for players in [vec![], vec![[50, 50, 0]]] {
        assert!(ordinary_path(
            &roster,
            &players,
            &indexed,
            &HashSet::new(),
            20,
            1,
            &|_| true,
            None,
            &mut StdRng::seed_from_u64(1)
        )
        .unwrap()
        .is_none());
    }
    assert!(near(&[a], &[[20, -20, 0]], 20));
    assert!(!near(&[a], &[[21, 0, 0]], 20));
    let plan = run(&roster, &[[2, 0, 0]], &[(a, b)], &[], |_| true).unwrap();
    assert_eq!(point(&plan.members[0]).unwrap(), b);
    assert_eq!(point(&roster[0]).unwrap(), a);
}
#[test]
fn one_and_three_height_steps_serialize_only_verified_native_edges() {
    let cells = [[0, 0, 0], [1, 0, 2], [1, 1, 1], [0, 1, 0]];
    let indexed = graph(&[
        (cells[0], cells[1]),
        (cells[1], cells[2]),
        (cells[2], cells[3]),
    ]);
    for (requested, expected) in [(1, 1), (3, 3), (8, 3)] {
        let plan = ordinary_path(
            &[actor(-200, cells[0])],
            &[[10, 10, 0]],
            &indexed,
            &HashSet::new(),
            20,
            requested,
            &|_| true,
            None,
            &mut StdRng::seed_from_u64(1),
        )
        .unwrap()
        .unwrap();
        let (id, start, path) = decode_packet(&plan.packets[0]).unwrap();
        assert_eq!(id, -200);
        assert_eq!(start, cells[0]);
        assert_eq!(path, &cells[1..=expected]);
        assert_eq!(point(&plan.members[0]).unwrap(), cells[expected]);
    }
}
#[test]
fn each_path_step_checks_habitat_before_entry() {
    let a = [0, 0, 0];
    let b = [1, 0, 0];
    let c = [2, 0, 0];
    let checked = std::cell::RefCell::new(Vec::new());
    let plan = ordinary_path(
        &[actor(-1, a)],
        &[[10, 0, 0]],
        &graph(&[(a, b), (b, c)]),
        &HashSet::new(),
        20,
        3,
        &|p| {
            checked.borrow_mut().push(p);
            p == b
        },
        None,
        &mut StdRng::seed_from_u64(1),
    )
    .unwrap()
    .unwrap();
    assert_eq!(*checked.borrow(), vec![b, c]);
    assert_eq!(point(&plan.members[0]).unwrap(), b);
    assert_eq!(decode_packet(&plan.packets[0]).unwrap().2, vec![b]);
}
fn crowded() -> (Vec<Value>, Vec<(Point, Point)>, Vec<Point>) {
    (
        vec![actor(-1, [-57, 8, 0]), actor(-2, [-59, 11, 0])],
        vec![
            ([-57, 8, 0], [-57, 9, 0]),
            ([-57, 8, 0], [-56, 8, 0]),
            ([-57, 8, 0], [-58, 8, 0]),
            ([-57, 8, 0], [-57, 7, 0]),
            ([-59, 11, 0], [-60, 11, 0]),
            ([-59, 11, 0], [-59, 10, 0]),
            ([-59, 11, 0], [-58, 11, 0]),
        ],
        vec![[-56, 8, 0], [-58, 8, 0], [-57, 7, 0]],
    )
}
#[test]
fn crowded_mixed_species_move_leader_while_companion_holds() {
    for refs in [[5525, 5525], [2616, 2617], [2598, 2616], [39, 2616]] {
        let (mut roster, edges, blocked) = crowded();
        for (member, r) in roster.iter_mut().zip(refs) {
            member["ref"] = json!(r);
        }
        let plan = run(&roster, &[[-63, 8, 0]], &edges, &blocked, |_| true).unwrap();
        assert_eq!(
            member_points(&plan.members).unwrap(),
            vec![[-57, 9, 0], [-59, 11, 0]]
        );
        assert_eq!(plan.packets.len(), 1);
        assert_eq!(
            member_points(&roster).unwrap(),
            vec![[-57, 8, 0], [-59, 11, 0]]
        );
        assert_eq!(
            plan.members
                .iter()
                .map(|m| m["ref"].as_i64().unwrap())
                .collect::<Vec<_>>(),
            refs
        );
    }
}
#[test]
fn crowded_no_players_zero_radius_and_habitat_rejection() {
    let (roster, edges, blocked) = crowded();
    let indexed = graph(&edges);
    let occupied = blocked.into_iter().collect();
    for (players, radius) in [(vec![], 20), (vec![[-57, 8, 0]], 0)] {
        assert!(group_path(
            &roster,
            &players,
            &[],
            &indexed,
            &occupied,
            radius,
            1,
            1,
            &|_| true,
            &mut StdRng::seed_from_u64(1)
        )
        .unwrap()
        .is_none());
    }
    let plan = run(
        &roster,
        &[[-63, 8, 0]],
        &edges,
        &[[-56, 8, 0], [-58, 8, 0], [-57, 7, 0]],
        |p| p != [-57, 9, 0],
    )
    .unwrap();
    assert_eq!(point(&plan.members[0]).unwrap(), [-57, 8, 0]);
    assert!(member_points(&plan.members)
        .unwrap()
        .iter()
        .all(|p| *p != [-57, 9, 0]));
}
#[test]
fn fallback_cannot_cross_held_companion_or_increase_cohesion_past_limit() {
    for companion in [[1, 0, 0], [-4, 0, 0]] {
        assert!(run(
            &[actor(-1, [0, 0, 0]), actor(-2, companion)],
            &[[0, 2, 0]],
            &[([0, 0, 0], [1, 0, 0])],
            &[],
            |_| true
        )
        .is_none());
    }
}
#[test]
fn blocked_leader_can_hold_while_companion_advances() {
    let plan = run(
        &[actor(-1, [0, 0, 0]), actor(-2, [0, 1, 0])],
        &[[0, 3, 0]],
        &[([0, 0, 0], [1, 0, 0]), ([0, 1, 0], [1, 1, 0])],
        &[[1, 0, 0]],
        |_| true,
    )
    .unwrap();
    assert_eq!(
        member_points(&plan.members).unwrap(),
        vec![[0, 0, 0], [1, 1, 0]]
    );
    assert_eq!(plan.packets.len(), 1);
    assert_eq!(decode_packet(&plan.packets[0]).unwrap().0, -2);
}
#[test]
fn five_members_keep_formation_identity_and_one_group_probability_decision() {
    let roster: Vec<_> = (0..5).map(|i| actor(-200 - i, [i, 0, 0])).collect();
    let edges: Vec<_> = (0..5).map(|i| ([i, 0, 0], [i, 1, 0])).collect();
    let calls = std::cell::Cell::new(0);
    assert!(wander_admitted(false, true, 0.25, || {
        calls.set(calls.get() + 1);
        0.249
    }));
    let plan = run(&roster, &[[20, 10, 0]], &edges, &[], |_| true).unwrap();
    assert_eq!(calls.get(), 1);
    assert_eq!(plan.packets.len(), 5);
    for (before, after) in roster.iter().zip(plan.members) {
        assert_eq!(before["id"], after["id"]);
        assert_eq!(before["ref"], after["ref"]);
        assert_eq!(after["y"], 1);
    }
}
#[test]
fn independent_probability_boundary_and_harvest_excludes_entire_roster() {
    let calls = std::cell::Cell::new(0);
    let admitted: Vec<_> = [0.249, 0.25]
        .into_iter()
        .map(|roll| {
            wander_admitted(false, true, 0.25, || {
                calls.set(calls.get() + 1);
                roll
            })
        })
        .collect();
    assert_eq!(admitted, vec![true, false]);
    assert_eq!(calls.get(), 2);
    let roster: Vec<_> = (0..5).map(|i| actor(-210 - i, [i * 10, 0, 0])).collect();
    assert!(!autonomous_roster(&roster, &HashSet::from([-212])).unwrap());
    assert!(autonomous_roster(&roster, &HashSet::new()).unwrap());
}
#[test]
fn fixed_native_roster_is_excluded_before_probability_or_planning() {
    let mut fixed = actor(-1, [0, 0, 0]);
    fixed["fixed_actor_placement"] = json!({"reference":5525,"direction":3,"cell":[0,0,0],"source":{"kind":"original_native_marker","uri":"native:fixture","sha256":"a".repeat(64)}});
    assert!(!autonomous_roster(&[actor(-2, [1, 0, 0]), fixed.clone()], &HashSet::new()).unwrap());
    fixed["x"] = json!(1);
    assert!(autonomous_roster(&[fixed], &HashSet::new()).is_err());
}
#[test]
fn neighbor_radius_and_preferred_farther_legal_step_match_native_kernel() {
    let groups: Vec<_> = [0, 3, 40]
        .into_iter()
        .enumerate()
        .map(|(i, x)| json!({"status":"available","members":[actor(-(i as i64)-1,[x,0,0])]}))
        .collect();
    assert_eq!(
        nearest_group([0, 0, 0], -1, &groups).unwrap(),
        Some([3, 0, 0])
    );
    assert_eq!(nearest_group([40, 0, 0], -3, &groups).unwrap(), None);
    assert_eq!(
        choose(
            vec![vec![[-1, 0, 0]], vec![[1, 0, 0]]],
            &mut StdRng::seed_from_u64(1),
            Some([3, 0, 0]),
            [0, 0, 0]
        ),
        Some(vec![[-1, 0, 0]])
    );
    assert_eq!(
        choose(
            vec![vec![[1, 0, 0]]],
            &mut StdRng::seed_from_u64(1),
            Some([3, 0, 0]),
            [0, 0, 0]
        ),
        Some(vec![[1, 0, 0]])
    );
}
#[test]
fn far_population_uses_no_visible_budget_and_all_near_groups_rotate() {
    let mut groups: Vec<_> = (0..5000)
        .map(|i| json!({"group_id":i,"status":"available","members":[actor(-i-1,[10000+i,0,0])]}))
        .collect();
    groups.extend((0..50).map(
        |i| json!({"group_id":5000+i,"status":"available","members":[actor(-5001-i,[i,0,0])]}),
    ));
    let mut seen = HashSet::new();
    // Actual production fairness rotates one group per tick, not the obsolete
    // eight-group stride expected by the retired Python fixture.
    for tick in 0..50 {
        let selected = visible_groups(&groups, &[[0, 0, 0], [49, 0, 0]], 25, tick).unwrap();
        assert_eq!(selected.len(), 50);
        for group in selected.iter().take(8) {
            let id = group_id(group).unwrap();
            assert!(id >= 5000);
            seen.insert(id);
        }
    }
    assert_eq!(seen, (5000..5050).collect());
    let groups = [
        json!({"group_id":1,"status":"fighting","members":[actor(-1,[0,0,0])]}),
        json!({"group_id":2,"status":"available","members":[actor(-2,[10,-10,0])]}),
        json!({"group_id":3,"status":"available","members":[actor(-3,[11,0,0])]}),
    ];
    assert!(visible_groups(&groups, &[], 10, 0).unwrap().is_empty());
    assert_eq!(
        visible_groups(&groups, &[[0, 0, 0]], 10, 0)
            .unwrap()
            .iter()
            .map(|g| group_id(g).unwrap())
            .collect::<Vec<_>>(),
        vec![2]
    );
}
#[test]
fn seeded_dispersal_keeps_native_routes_varied_and_outward() {
    for origin in [[1, 0, 0], [0, 1, 0], [-1, 0, 0]] {
        let x = origin[0];
        let y = origin[1];
        let destinations: Vec<_> = [[1, 0], [-1, 0], [0, 1], [0, -1]]
            .into_iter()
            .map(|d| [x + d[0], y + d[1], 0])
            .filter(|p| distance(*p, [0, 0, 0]) > distance(origin, [0, 0, 0]))
            .collect();
        let edges: Vec<_> = destinations
            .iter()
            .flat_map(|p| [(origin, *p), (*p, [2 * p[0] - x, 2 * p[1] - y, 0])])
            .collect();
        let indexed = graph(&edges);
        let roster = [actor(-701, origin)];
        let others = [json!({"status":"available","members":[actor(-703,[0,0,0])]})];
        let mut routes = HashSet::new();
        let mut count = 0;
        for seed in 0..100 {
            if let Some(plan) = group_path(
                &roster,
                &[[x, y + 3, 0]],
                &others,
                &indexed,
                &destinations.iter().copied().collect(),
                20,
                2,
                2,
                &|_| true,
                &mut StdRng::seed_from_u64(seed),
            )
            .unwrap()
            {
                assert!(plan.dispersal);
                let p = point(&plan.members[0]).unwrap();
                assert!(distance(p, [0, 0, 0]) > distance(origin, [0, 0, 0]));
                routes.insert(p);
                count += 1;
            }
        }
        assert!(routes.len() > 1);
        assert!(count > 0 && count < 100);
    }
}
#[test]
fn dispersal_can_cross_actors_but_still_requires_habitat_and_clear_endpoints() {
    let roster = [actor(-701, [1, 0, 0]), actor(-702, [3, 0, 0])];
    let players = [[2, 0, 0]];
    let groups = [
        json!({"status":"available","members":[actor(-703,[0,0,0])]}),
        json!({"status":"available","members":[actor(-704,[2,0,0])]}),
    ];
    let edges: Vec<_> = (1..5).map(|x| ([x, 0, 0], [x + 1, 0, 0])).collect();
    let indexed = graph(&edges);
    let plan = dispersal_path(
        &roster,
        &players,
        &groups,
        &indexed,
        [0, 0, 0],
        20,
        3,
        &|_| true,
        &mut StdRng::seed_from_u64(1),
    )
    .unwrap()
    .unwrap();
    assert!(member_points(&plan.members)
        .unwrap()
        .iter()
        .all(|p| !players.contains(p) && *p != [0, 0, 0]));
    assert!(dispersal_path(
        &roster,
        &players,
        &groups,
        &indexed,
        [0, 0, 0],
        20,
        3,
        &|_| false,
        &mut StdRng::seed_from_u64(1)
    )
    .unwrap()
    .is_none());
    assert!(ordinary_path(
        &roster,
        &players,
        &indexed,
        &HashSet::from([[0, 0, 0], [2, 0, 0]]),
        20,
        3,
        &|_| true,
        None,
        &mut StdRng::seed_from_u64(1)
    )
    .unwrap()
    .is_none());
}

struct NoRandom;
impl rand::RngCore for NoRandom {
    fn next_u32(&mut self) -> u32 {
        panic!("Inactive planning spent randomness")
    }
    fn next_u64(&mut self) -> u64 {
        panic!("Inactive planning spent randomness")
    }
    fn fill_bytes(&mut self, _: &mut [u8]) {
        panic!("Inactive planning spent randomness")
    }
}
#[test]
fn inactive_players_never_consume_randomness_and_random_branch_skips_neighbor_lookup() {
    let roster = [actor(-1, [0, 0, 0])];
    let indexed = graph(&[([0, 0, 0], [1, 0, 0])]);
    assert!(group_path(
        &roster,
        &[],
        &[],
        &indexed,
        &HashSet::new(),
        20,
        1,
        1,
        &|_| true,
        &mut NoRandom
    )
    .unwrap()
    .is_none());
    assert!(group_path(
        &roster,
        &[[0, 2, 0]],
        &[],
        &indexed,
        &HashSet::new(),
        0,
        1,
        1,
        &|_| true,
        &mut NoRandom
    )
    .unwrap()
    .is_none());
    // A missing neighbor identity is harmless to external occupancy, but would
    // fail nearest_group. The ordinary branch must never ask for that identity.
    let groups = [json!({"status":"available","members":[{"x":3,"y":0,"z":0}]})];
    let seed = (0..100)
        .find(|seed| StdRng::seed_from_u64(*seed).random::<f64>() >= 0.5)
        .unwrap();
    assert!(group_path(
        &roster,
        &[[0, 2, 0]],
        &groups,
        &indexed,
        &HashSet::new(),
        20,
        1,
        1,
        &|_| true,
        &mut StdRng::seed_from_u64(seed)
    )
    .unwrap()
    .is_some());
}
