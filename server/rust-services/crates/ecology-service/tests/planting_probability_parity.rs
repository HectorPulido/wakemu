//! Regression cases migrated from the retired Python probability producer.
use wakemu_ecology::planners::planting_intents::probability;

#[test]
fn native_golden_probabilities_and_climate() {
    for (soil, compatible, bonus, expected) in [
        (1, true, 0.0, 0.01),
        (50, true, -50.0, 0.25),
        (50, true, 0.0, 0.5),
        (50, true, 50.0, 0.75),
        (100, true, 0.0, 1.0),
        (100, false, 0.0, 0.8),
        (70, false, 0.0, 0.7 * 0.8),
        (70, true, 0.0, 0.7),
        (0, true, 100.0, 0.0),
        (100, true, 25.0, 1.0),
        (51, true, -50.0, 0.255),
    ] {
        assert_eq!(probability(soil, compatible, bonus).unwrap(), expected);
    }
    assert_eq!(probability(50, true, 1.0).unwrap(), 0.5049999998882413);
}

#[test]
fn every_native_soil_and_profession_level_stays_bounded_and_monotone() {
    for soil in 0..=100 {
        for compatible in [true, false] {
            let mut previous = 0.0;
            for level in 0..=200 {
                let chance = probability(soil, compatible, (level / 2) as f64).unwrap();
                assert!(chance >= previous && chance <= 1.0);
                assert_eq!(chance == 0.0, soil == 0);
                previous = chance;
            }
        }
    }
}

#[test]
fn malformed_numeric_policy_is_rejected() {
    for soil in [-1, 101, i64::MAX] {
        assert!(probability(soil, true, 0.0).is_err());
    }
    for bonus in [
        f64::NAN,
        f64::INFINITY,
        f64::NEG_INFINITY,
        2147483648.0,
        -2147483649.0,
    ] {
        assert!(probability(50, true, bonus).is_err());
    }
}

#[test]
#[ignore = "requires the native Java oracle matrix in WAKFU_PLANTING_NATIVE_ORACLE"]
fn native_java_matrix_matches_production_probability_when_supplied() {
    let path = std::env::var("WAKFU_PLANTING_NATIVE_ORACLE")
        .expect("WAKFU_PLANTING_NATIVE_ORACLE must identify the native Java matrix");
    let source = std::fs::read_to_string(path).unwrap();
    let mut lines = source.lines();
    let headers: Vec<_> = lines.next().unwrap().split(',').collect();
    let column = |name| headers.iter().position(|value| *value == name).unwrap();
    let mut count = 0;
    for line in lines {
        let values: Vec<_> = line.split(',').collect();
        let chance = probability(
            values[column("terrain")].parse().unwrap(),
            values[column("compatible")] == "true",
            values[column("bonus")].parse().unwrap(),
        )
        .unwrap();
        assert_eq!(
            chance,
            values[column("probability")].parse::<f64>().unwrap(),
            "{line}"
        );
        count += 1;
    }
    assert_eq!(count, 60802);
}
