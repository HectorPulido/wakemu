//! Ports of every assertion in test_monster_birth_home.py and the home movement
//! scenarios. Visible-group rotation is already exercised by the production
//! mob_geometry::tests::visible_group_rotation_preserves_one_position_stride_and_reaches_the_end.
use super::*;
use std::collections::{BTreeSet, HashMap, HashSet};

async fn provenance_schema(f: &Fixture) -> Result<()> {
    let db = f.ctx.db.get().await?;
    db.batch_execute("DROP TABLE monster_group_birth_homes;
        ALTER TABLE planting_growth_outbox ADD COLUMN IF NOT EXISTS resource_uid bigint;
        ALTER TABLE planting_receipts ADD COLUMN IF NOT EXISTS operation_id text;
        CREATE TABLE monster_initial_population(map_id integer,instance_id bigint,region_id integer,group_id bigint,initial_members jsonb);
        CREATE TABLE monster_reproduction_receipts(map_id integer,instance_id bigint,monster_id bigint,cycle bigint,parent_group_id bigint,parent_reference integer,child_id bigint,child_group_id bigint,child jsonb);
        CREATE TABLE archmonster_spawn_births(map_id integer,world_instance_id bigint,group_id bigint,region_id integer,spawn_id text);
        CREATE TABLE environmental_event_instances(instance_id bigint,region_id integer);
        CREATE TABLE environmental_owned_groups(map_id integer,world_instance_id bigint,group_id bigint,instance_id bigint,group_ordinal integer);
        CREATE TABLE ecology_admin_operations(id bigint GENERATED ALWAYS AS IDENTITY,command text,outcome jsonb);").await?;
    db.batch_execute(include_str!(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../../migrations/323_monster_birth_home.sql"
    )))
    .await?;
    Ok(())
}
async fn insert_group(
    f: &Fixture,
    map: i32,
    gid: i64,
    status: &str,
    roster: &[Value],
) -> Result<()> {
    f.ctx.db.get().await?.execute("INSERT INTO combat_groups(map_id,instance_id,group_id,status,members) VALUES($1,0,$2,$3,$4)",&[&map,&gid,&status,&json!(roster)]).await?;
    Ok(())
}
async fn insert_home(f: &Fixture, map: i32, gid: i64, region: i32) -> Result<()> {
    f.ctx.db.get().await?.execute("INSERT INTO monster_group_birth_homes(map_id,instance_id,group_id,region_id,source_kind,source_key,anchor) VALUES($1,0,$2,$3,'initial_population','fixed-history','[0,0,0]')",&[&map,&gid,&region]).await?;
    Ok(())
}
fn group(gid: i64, status: &str, roster: &[Value]) -> Value {
    json!({"group_id":gid,"status":status,"members":roster})
}
async fn terrain(f: &Fixture, map: i32, region_cells: &[(i32, Vec<[i64; 2]>)]) -> Result<()> {
    let rows: Vec<Value> = region_cells
        .iter()
        .map(|(region, cells)| json!({"region_id":region,"cells":cells}))
        .collect();
    f.document(
        "territory-map-cells.json",
        json!({"schema_version":1,"grid_size":18,"maps":[{"map_id":map,"regions":rows}]}),
    )
    .await?;
    f.document("ecology-regions.json", json!([])).await
}
async fn graph(
    f: &Fixture,
    map: i32,
    cells: &[[i64; 3]],
    edges: &[([i64; 3], [i64; 3])],
) -> Result<()> {
    f.document(
        &format!("combat-maps/{map}.json"),
        json!({"map_id":map,"cells":cells,"edges":edges}),
    )
    .await
}
fn rectangle(width: i64, height: i64) -> (Vec<[i64; 3]>, Vec<([i64; 3], [i64; 3])>) {
    let mut cells = Vec::new();
    let mut edges = Vec::new();
    for x in 0..width {
        for y in 0..height {
            let p = [x, y, 0];
            cells.push(p);
            for (dx, dy) in [(1, 0), (-1, 0), (0, 1), (0, -1)] {
                let q = [x + dx, y + dy, 0];
                if (0..width).contains(&q[0]) && (0..height).contains(&q[1]) {
                    edges.push((p, q));
                }
            }
        }
    }
    (cells, edges)
}
fn point_member(id: i64, map: i32, point: [i64; 3]) -> Value {
    let mut row = member(4, id, map as i64, point[0], point[1]);
    row["z"] = json!(point[2]);
    row
}
fn unchanged_owned(before: &Value, after: &Value) {
    let mut before = before.as_object().unwrap().clone();
    let mut after = after.as_object().unwrap().clone();
    for key in ["x", "y", "z"] {
        before.remove(key);
        after.remove(key);
    }
    assert_eq!(before, after);
}
fn packet_path(packet: &Value) -> Result<(i64, Vec<[i64; 3]>)> {
    assert_eq!(packet[0], 13852);
    let bytes = hex::decode(packet[1].as_str().context("Native movement hex")?)?;
    ensure!(bytes.len() >= 19, "Truncated native movement");
    let id = i64::from_be_bytes(bytes[..8].try_into()?);
    let p = [
        i32::from_be_bytes(bytes[8..12].try_into()?) as i64,
        i32::from_be_bytes(bytes[12..16].try_into()?) as i64,
        i16::from_be_bytes(bytes[16..18].try_into()?) as i64,
    ];
    let count = bytes[18] as usize;
    assert_eq!(bytes.len(), 19 + count);
    let mut path = vec![p];
    let directions = [
        [1, -1],
        [1, 0],
        [1, 1],
        [0, 1],
        [-1, 1],
        [-1, 0],
        [-1, -1],
        [0, -1],
    ];
    for byte in &bytes[19..] {
        let delta = directions[(byte >> 5) as usize];
        let dz = (*byte & 31) as i64;
        let dz = if dz >= 16 { dz - 32 } else { dz };
        let prev = *path.last().unwrap();
        path.push([prev[0] + delta[0], prev[1] + delta[1], prev[2] + dz]);
    }
    Ok((id, path))
}
async fn wander(
    f: &Fixture,
    map: i32,
    roster: &[Value],
    blockers: &[Value],
    edges: &[([i64; 3], [i64; 3])],
    steps: i64,
    overlap: bool,
) -> Result<Option<Value>> {
    let cells: BTreeSet<_> = edges
        .iter()
        .flat_map(|(a, b)| [*a, *b])
        .chain(roster.iter().map(|m| mob_geometry::point(m).unwrap()))
        .collect();
    graph(f, map, &cells.into_iter().collect::<Vec<_>>(), edges).await?;
    terrain(
        f,
        map,
        &[(11, vec![[-1, -1], [-1, 0]]), (22, vec![[0, -1], [0, 0]])],
    )
    .await?;
    let mut groups = vec![group(1, "available", roster)];
    groups.extend_from_slice(blockers);
    let player = if overlap {
        mob_geometry::point(&roster[0])?
    } else {
        [2, 3, 0]
    };
    let snapshot = json!({"world_epoch":format!("native-home-{map}"),"players":[{"id":8,"map_id":map,"instance_id":0,"x":player[0],"y":player[1],"z":player[2]}],"excluded_ids":[],"allow_wander":true,"domain_planning_tick":0});
    let config = json!({"interval_seconds":1,"move_probability":1.0,"radius":20,"min_steps":steps,"max_steps":steps});
    mob_geometry::prepare_scope_wander(
        &f.ctx,
        &snapshot,
        [map as i64, 0],
        &groups,
        &config,
        &HashMap::from([(1, 11)]),
    )
    .await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn reported_tainela_walk_step_crosses_an_exact_birth_territory_boundary() -> Result<()> {
    let f = Fixture::new().await?;
    terrain(
        &f,
        527,
        &[(76101, vec![[-12, -4]]), (76001, vec![[-11, -4]])],
    )
    .await?;
    f.document(
        "planting-maps/527.json",
        json!({"cells":[[-199,-67,0,0,0,76101],[-198,-67,0,0,0,76001]]}),
    )
    .await?;
    assert_eq!(
        mob_geometry::region_for_point(&f.ctx, 527, [-199, -67, 0]).await?,
        76101
    );
    assert_eq!(
        mob_geometry::region_for_point(&f.ctx, 527, [-198, -67, 0]).await?,
        76001
    );
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn history_dead_parent_and_foreign_planting_win_over_current_position() -> Result<()> {
    let f = Fixture::new().await?;
    provenance_schema(&f).await?;
    let map = 999999i32;
    terrain(&f, map, &[(11, vec![[0, 0]]), (22, vec![[1, 0]])]).await?;
    let parent = point_member(-9101, map, [20, 0, 0]);
    let child = point_member(-9102, map, [25, 0, 0]);
    let mut foreign = point_member(-9103, map, [22, 0, 0]);
    foreign["ref"] = json!(9999);
    let unknown = point_member(-9104, map, [27, 0, 0]);
    let genesis = point_member(-9105, map, [25, 0, 0]);
    let all = vec![
        group(9101, "defeated", &[parent.clone()]),
        group(9102, "available", &[child.clone()]),
        group(9103, "available", &[foreign.clone()]),
        group(9104, "available", &[unknown.clone()]),
        group(9105, "available", &[genesis.clone()]),
    ];
    for g in &all {
        insert_group(
            &f,
            map,
            g["group_id"].as_i64().unwrap(),
            g["status"].as_str().unwrap(),
            g["members"].as_array().unwrap(),
        )
        .await?;
    }
    let db = f.ctx.db.get().await?;
    db.execute(
        "INSERT INTO monster_initial_population VALUES($1,0,11,9101,$2)",
        &[&map, &json!([point_member(-9101, map, [0, 0, 0])])],
    )
    .await?;
    db.execute(
        "INSERT INTO monster_reproduction_receipts VALUES($1,0,-9101,1,9101,4,-9102,9102,$2)",
        &[&map, &point_member(-9102, map, [21, 0, 0])],
    )
    .await?;
    let resource = json!({"map_id":map,"instance_id":0,"x":3,"y":0,"z":0});
    db.execute("INSERT INTO planting_growth_outbox(resource_uid,resource,group_payload) VALUES(991003,$1,$2)",&[&resource,&json!({"key":[map,0,9103],"members":[foreign]})]).await?;
    db.execute(
        "INSERT INTO ecology_admin_operations(command,outcome) VALUES('!genesis',$1)",
        &[&json!({"scopes":[[map,0,11]],"created_groups":[{"key":[map,0,9105]}]})],
    )
    .await?;
    drop(db);
    let requested = all[1..].to_vec();
    let homes = mob_geometry::ensure_homes(&f.ctx, [map as i64, 0], &requested).await?;
    assert_eq!(
        homes,
        HashMap::from([(9102, 11), (9103, 11), (9104, 22), (9105, 11)])
    );
    let db = f.ctx.db.get().await?;
    let ledger: HashMap<i64, Value> = db
        .query(
            "SELECT group_id,to_jsonb(h) FROM monster_group_birth_homes h",
            &[],
        )
        .await?
        .into_iter()
        .map(|r| (r.get(0), r.get(1)))
        .collect();
    assert_eq!(ledger[&9101]["region_id"], 11);
    assert_eq!(ledger[&9101]["source_kind"], "initial_population");
    assert_eq!(ledger[&9102]["source_kind"], "reproduction_parent");
    assert_eq!(ledger[&9102]["source_key"], "9101");
    assert_eq!(ledger[&9103]["source_kind"], "planting");
    assert_eq!(ledger[&9104]["source_kind"], "legacy_current_fallback");
    assert_eq!(ledger[&9104]["anchor"], json!([27, 0, 0]));
    assert_eq!(ledger[&9105]["source_kind"], "genesis_scope");
    assert!(ledger[&9105]["anchor"].is_null());
    let durable: HashMap<i64, Value> = db
        .query("SELECT group_id,members FROM combat_groups", &[])
        .await?
        .into_iter()
        .map(|r| (r.get(0), r.get(1)))
        .collect();
    for g in &all {
        assert_eq!(durable[&g["group_id"].as_i64().unwrap()], g["members"]);
    }
    let moved = point_member(-9104, map, [0, 0, 0]);
    db.execute(
        "UPDATE combat_groups SET members=$1 WHERE group_id=9104",
        &[&json!([moved.clone()])],
    )
    .await?;
    // Existing homes must return before provenance is consulted again.
    db.batch_execute("DROP TABLE ecology_admin_operations")
        .await?;
    drop(db);
    let mut later = requested;
    later[2]["members"] = json!([moved]);
    assert_eq!(
        mob_geometry::ensure_homes(&f.ctx, [map as i64, 0], &later).await?,
        homes
    );
    let db = f.ctx.db.get().await?;
    let error = db
        .execute(
            "UPDATE monster_group_birth_homes SET region_id=99 WHERE group_id=9104",
            &[],
        )
        .await
        .unwrap_err();
    assert!(error
        .as_db_error()
        .is_some_and(|error| error.message().contains("immutable")));
    assert_eq!(
        db.query_one(
            "SELECT region_id FROM monster_group_birth_homes WHERE group_id=9104",
            &[]
        )
        .await?
        .get::<_, i32>(0),
        22
    );
    drop(db);
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn unknown_defeated_positions_do_not_block_living_empty_scope_distribution() -> Result<()> {
    let f = Fixture::new().await?;
    provenance_schema(&f).await?;
    let map = 999997i32;
    let (cells, edges) = rectangle(8, 8);
    graph(&f, map, &cells, &edges).await?;
    terrain(&f, map, &[(11, vec![[0, 0]])]).await?;
    let living = point_member(-9401, map, [10, 0, 0]);
    let mut defeated = point_member(-9402, map, [1000000, 1000000, 0]);
    defeated["hp"] = json!(0);
    insert_group(&f, map, 9401, "available", &[living.clone()]).await?;
    insert_group(&f, map, 9402, "defeated", &[defeated.clone()]).await?;
    insert_home(&f, map, 9401, 11).await?;
    assert!(mob_geometry::ensure_homes(
        &f.ctx,
        [map as i64, 0],
        &[group(9402, "defeated", &[defeated.clone()])]
    )
    .await
    .is_err());
    let snapshot = json!({"world_epoch":"living-after-history","empty_scopes":[{"map_id":map,"instance_id":0,"empty_generation":1}]});
    let proposals = mob_idle::prepare(&f.ctx, &snapshot, 1).await?;
    assert_eq!(proposals.len(), 1);
    assert!(mob_idle::home_chunk_allowed(&f.ctx, &proposals[0]).await?);
    let moves = mob_idle::read_chunk(&f.ctx, &proposals[0]).await?;
    assert_eq!(moves.len(), 1);
    assert_eq!(moves[0]["group_id"], 9401);
    assert_eq!(moves[0]["expected_members"], json!([living.clone()]));
    assert_ne!(moves[0]["moved_members"], json!([living.clone()]));
    assert_eq!(mob_idle::prepare(&f.ctx, &snapshot, 1).await?, proposals);
    let db = f.ctx.db.get().await?;
    assert!(db
        .query_opt(
            "SELECT 1 FROM monster_group_birth_homes WHERE group_id=9402",
            &[]
        )
        .await?
        .is_none());
    let rows = db
        .query(
            "SELECT group_id,status,members,revision FROM combat_groups ORDER BY group_id",
            &[],
        )
        .await?;
    assert_eq!(rows[0].get::<_, Value>(2), json!([living]));
    assert_eq!(rows[1].get::<_, Value>(2), json!([defeated]));
    assert_eq!(rows[1].get::<_, String>(1), "defeated");
    assert!(rows.iter().all(|r| r.get::<_, i64>(3) == 0));
    drop(db);
    f.close().await
}
async fn frozen(
    f: &Fixture,
    map: i32,
    epoch: &str,
    generation: i64,
    old: &Value,
    new: &Value,
) -> Result<i64> {
    let db = f.ctx.db.get().await?;
    let run:i64=db.query_one("INSERT INTO monster_idle_distribution_runs(world_epoch,map_id,instance_id,empty_generation,status) VALUES($1,$2,0,$3,'pending') RETURNING id",&[&epoch,&map,&generation]).await?.get(0);
    db.execute("INSERT INTO monster_idle_distribution_moves(run_id,ordinal,chunk_index,group_id,expected_members,moved_members) VALUES($1,0,0,9301,$2,$3)",&[&run,&json!([old]),&json!([new])]).await?;
    Ok(run)
}
#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn old_frozen_idle_plan_outside_home_is_cancelled_before_ecology_delivery() -> Result<()> {
    let f = Fixture::new().await?;
    provenance_schema(&f).await?;
    let map = 999998i32;
    terrain(&f, map, &[(11, vec![[0, 0]]), (22, vec![[1, 0]])]).await?;
    let old = point_member(-9301, map, [0, 0, 0]);
    insert_group(&f, map, 9301, "available", &[old.clone()]).await?;
    insert_home(&f, map, 9301, 11).await?;
    let run = frozen(
        &f,
        map,
        "frozen-home",
        1,
        &old,
        &point_member(-9301, map, [20, 0, 0]),
    )
    .await?;
    let mut snapshot = json!({"world_epoch":"frozen-home","empty_scopes":[{"map_id":map,"instance_id":0,"empty_generation":1}]});
    assert!(mob_idle::prepare(&f.ctx, &snapshot, 1).await?.is_empty());
    assert!(mob_idle::prepare(&f.ctx, &snapshot, 1).await?.is_empty());
    let db = f.ctx.db.get().await?;
    assert_eq!(
        db.query_one(
            "SELECT status FROM monster_idle_distribution_runs WHERE id=$1",
            &[&run]
        )
        .await?
        .get::<_, String>(0),
        "cancelled"
    );
    assert_eq!(
        db.query_one(
            "SELECT status FROM monster_idle_distribution_moves WHERE run_id=$1",
            &[&run]
        )
        .await?
        .get::<_, String>(0),
        "cancelled"
    );
    drop(db);
    frozen(
        &f,
        map,
        "frozen-home",
        2,
        &old,
        &point_member(-9301, map, [2, 0, 0]),
    )
    .await?;
    snapshot["empty_scopes"][0]["empty_generation"] = json!(2);
    let delivered = mob_idle::prepare(&f.ctx, &snapshot, 1).await?;
    assert_eq!(delivered.len(), 1);
    assert_eq!(delivered[0]["empty_generation"], 2);
    let db = f.ctx.db.get().await?;
    let row = db
        .query_one(
            "SELECT members,revision FROM combat_groups WHERE group_id=9301",
            &[],
        )
        .await?;
    assert_eq!(row.get::<_, Value>(0), json!([old]));
    assert_eq!(row.get::<_, i64>(1), 0);
    assert_eq!(
        db.query_one(
            "SELECT region_id FROM monster_group_birth_homes WHERE group_id=9301",
            &[]
        )
        .await?
        .get::<_, i32>(0),
        11
    );
    drop(db);
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn split_group_keeps_roaming_inside_home_when_companion_cannot_return() -> Result<()> {
    for (index, mode) in ["blocked", "disconnected", "returning"]
        .into_iter()
        .enumerate()
    {
        let f = Fixture::new().await?;
        let map = 999990 + index as i32;
        let mut edges = vec![([-1, 1, 0], [-1, 2, 0]), ([-1, 1, 0], [0, 1, 0])];
        if mode != "disconnected" {
            edges.extend([([1, 0, 0], [0, 0, 0]), ([0, 0, 0], [-1, 0, 0])]);
        }
        let roster = vec![
            point_member(-1, map, [-1, 1, 0]),
            point_member(-2, map, [1, 0, 0]),
        ];
        let initial = roster.clone();
        let blockers = if mode == "blocked" {
            vec![group(2, "fighting", &[point_member(-99, map, [0, 0, 0])])]
        } else {
            vec![]
        };
        let plan = wander(&f, map, &roster, &blockers, &edges, 1, false)
            .await?
            .context("Split group must retain safe native movement")?;
        let movement = &plan["moves"][0];
        let moved = movement["moved_members"].as_array().unwrap();
        assert_eq!(mob_geometry::point(&moved[0])?, [-1, 2, 0]);
        assert_eq!(
            mob_geometry::point(&moved[1])?,
            if mode == "returning" {
                [0, 0, 0]
            } else {
                [1, 0, 0]
            }
        );
        for (old, new) in roster.iter().zip(moved) {
            unchanged_owned(old, new);
        }
        for packet in movement["packets"].as_array().unwrap() {
            let (id, path) = packet_path(packet)?;
            assert_eq!(path.len(), 2);
            assert!(edges.contains(&(path[0], path[1])));
            if mode == "blocked" {
                assert_ne!(path[1], [0, 0, 0]);
            }
            if id == -1 {
                assert_eq!(
                    mob_geometry::region_for_point(&f.ctx, map as i64, path[1]).await?,
                    11
                );
            }
        }
        let anchor = mob_geometry::point(&moved[0])?;
        for member in moved {
            let p = mob_geometry::point(member)?;
            assert!((p[0] - anchor[0]).abs().max((p[1] - anchor[1]).abs()) <= 2);
        }
        assert_eq!(roster, initial);
        f.close().await?;
    }
    Ok(())
}
#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn drifted_monster_returns_through_native_steps_without_teleporting_or_new_flags(
) -> Result<()> {
    for (index, mode) in ["returning", "blocked", "disconnected"]
        .into_iter()
        .enumerate()
    {
        let f = Fixture::new().await?;
        let map = 999980 + index as i32;
        let roster = vec![point_member(-1, map, [1, 0, 0])];
        let edges = if mode == "disconnected" {
            vec![]
        } else {
            vec![([1, 0, 0], [0, 0, 0]), ([0, 0, 0], [-1, 0, 0])]
        };
        let blockers = if mode == "blocked" {
            vec![group(2, "fighting", &[point_member(-99, map, [0, 0, 0])])]
        } else {
            vec![]
        };
        let plan = wander(&f, map, &roster, &blockers, &edges, 3, false).await?;
        if mode != "returning" {
            assert!(plan.is_none());
        } else {
            let plan = plan.context("Native home return expected")?;
            let movement = &plan["moves"][0];
            let moved = &movement["moved_members"][0];
            assert_eq!(mob_geometry::point(moved)?, [-1, 0, 0]);
            unchanged_owned(&roster[0], moved);
            assert!(movement.get("dispersal").is_none());
            assert!(movement.get("overlap_escape").is_none());
            let (id, path) = packet_path(&movement["packets"][0])?;
            assert_eq!(id, -1);
            assert_eq!(path, vec![[1, 0, 0], [0, 0, 0], [-1, 0, 0]]);
        }
        f.close().await?;
    }
    Ok(())
}
#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn homing_keeps_home_members_in_place_while_drifted_companions_return() -> Result<()> {
    let f = Fixture::new().await?;
    let map = 999970i32;
    let roster = vec![
        point_member(-1, map, [-1, 1, 0]),
        point_member(-2, map, [1, 0, 0]),
    ];
    let edges = vec![([1, 0, 0], [0, 0, 0]), ([0, 0, 0], [-1, 0, 0])];
    let plan = wander(&f, map, &roster, &[], &edges, 3, false)
        .await?
        .context("Native companion return expected")?;
    let movement = &plan["moves"][0];
    assert_eq!(movement["moved_members"][0], roster[0]);
    assert_eq!(
        mob_geometry::point(&movement["moved_members"][1])?,
        [-1, 0, 0]
    );
    let packets = movement["packets"].as_array().unwrap();
    assert_eq!(packets.len(), 1);
    assert_eq!(packet_path(&packets[0])?.0, -2);
    f.close().await
}
#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn roaming_dispersal_overlap_and_flexible_paths_cannot_leave_home() -> Result<()> {
    for (index, (overlap, companion)) in [(false, false), (true, false), (false, true)]
        .into_iter()
        .enumerate()
    {
        let f = Fixture::new().await?;
        let map = 999960 + index as i32;
        let edges = vec![
            ([-1, 0, 0], [0, 0, 0]),
            ([-1, 0, 0], [-1, 1, 0]),
            ([-1, 1, 0], [0, 1, 0]),
            ([-1, 1, 0], [-1, 2, 0]),
        ];
        let mut roster = vec![point_member(-1, map, [-1, 0, 0])];
        if companion {
            roster.push(point_member(-3, map, [-1, -1, 0]));
        }
        let threat = vec![group(2, "fighting", &[point_member(-2, map, [-2, 0, 0])])];
        let plan = wander(&f, map, &roster, &threat, &edges, 3, overlap)
            .await?
            .context("Safe home movement expected")?;
        let movement = &plan["moves"][0];
        for (old, new) in roster
            .iter()
            .zip(movement["moved_members"].as_array().unwrap())
        {
            unchanged_owned(old, new);
        }
        for packet in movement["packets"].as_array().unwrap() {
            let (_, path) = packet_path(packet)?;
            for step in path.windows(2) {
                assert!(edges.contains(&(step[0], step[1])));
                assert_eq!(
                    mob_geometry::region_for_point(&f.ctx, map as i64, step[1]).await?,
                    11
                );
            }
        }
        f.close().await?;
    }
    Ok(())
}
async fn idle_home_case(radius: i64) -> Result<()> {
    let f = Fixture::with_radius(radius).await?;
    let map = if radius == 0 { 999950 } else { 999951 };
    let (cells, edges) = rectangle(36, 24);
    graph(&f, map, &cells, &edges).await?;
    terrain(
        &f,
        map,
        &[(11, vec![[0, 0], [0, 1]]), (22, vec![[1, 0], [1, 1]])],
    )
    .await?;
    let mut groups = Vec::new();
    if radius == 0 {
        for (gid, home, x, y) in [(1, 11, 24, 2), (2, 22, 2, 18)] {
            let mut roster = Vec::new();
            for i in 0..3 {
                let mut row = point_member(-gid * 10 - i, map, [x + i, y, 0]);
                row["hp"] = json!(17 + i);
                row["level"] = json!(10 + i);
                roster.push(row);
            }
            f.group(map, gid, json!(roster), home).await?;
            groups.push(group(gid, "available", &roster));
        }
        let fighting = point_member(-30, map, [28, 20, 0]);
        f.group(map, 3, json!([fighting.clone()]), 22).await?;
        f.ctx
            .db
            .get()
            .await?
            .execute(
                "UPDATE combat_groups SET status='fighting' WHERE group_id=3",
                &[],
            )
            .await?;
        groups.push(group(3, "fighting", &[fighting]));
    } else {
        let row = point_member(-10, map, [24, 3, 0]);
        f.group(map, 1, json!([row.clone()]), 11).await?;
        groups.push(group(1, "available", &[row]));
    }
    let snapshot = json!({"world_epoch":format!("idle-homes-{map}"),"empty_scopes":[{"map_id":map,"instance_id":0,"empty_generation":1}]});
    let proposals = mob_idle::prepare(&f.ctx, &snapshot, 16).await?;
    let mut moves = Vec::new();
    for p in &proposals {
        assert!(mob_idle::home_chunk_allowed(&f.ctx, p).await?);
        moves.extend(mob_idle::read_chunk(&f.ctx, p).await?);
    }
    assert_eq!(
        moves
            .iter()
            .map(|m| m["group_id"].as_i64().unwrap())
            .collect::<HashSet<_>>(),
        if radius == 0 {
            HashSet::from([1, 2])
        } else {
            HashSet::from([1])
        }
    );
    let mut claimed = HashSet::new();
    for movement in &moves {
        let home = if movement["group_id"] == 1 { 11 } else { 22 };
        for (old, new) in movement["expected_members"]
            .as_array()
            .unwrap()
            .iter()
            .zip(movement["moved_members"].as_array().unwrap())
        {
            unchanged_owned(old, new);
            for p in mob_geometry::footprint(mob_geometry::point(new)?, radius)? {
                assert_eq!(
                    mob_geometry::region_for_point(&f.ctx, map as i64, p).await?,
                    home
                );
                assert!(
                    cells.contains(&p),
                    "Idle footprint left native exported terrain"
                );
                assert!(claimed.insert(p));
            }
        }
    }
    let db = f.ctx.db.get().await?;
    for g in groups {
        let row = db
            .query_one(
                "SELECT members,revision,status FROM combat_groups WHERE group_id=$1",
                &[&g["group_id"].as_i64().unwrap()],
            )
            .await?;
        assert_eq!(row.get::<_, Value>(0), g["members"]);
        assert_eq!(row.get::<_, i64>(1), 0);
        assert_eq!(row.get::<_, String>(2), g["status"].as_str().unwrap());
    }
    drop(db);
    f.close().await
}
#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn idle_distribution_uses_each_home_and_full_footprints_after_prior_drift() -> Result<()> {
    idle_home_case(0).await
}
#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn idle_large_footprint_cannot_straddle_its_birth_boundary() -> Result<()> {
    idle_home_case(1).await
}
