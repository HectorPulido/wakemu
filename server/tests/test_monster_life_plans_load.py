"""The former 5,000-actor creation/load test now executes native Rust.

Coverage: tests/lifecycle_contract.rs::
five_thousand_actors_use_batched_attach_and_noop_resolution, including bounded
statement writes, 5,000 receipts, zero due timers, and no player/queue rewards.
World plan fencing and failure charging remain in test_monster_life_plans.py.
"""
