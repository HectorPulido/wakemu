# Ecology contract fixtures

`python-contract-v1.jsonl` contains 33 expected outputs captured from the Python ecology service before its removal. Source SHA-256: `1a7438d59cef8a5c5d50e2257a67308162ee97939f5c04752bfd73965d1a7e98` (`server/ecology-service/service.py`). The inputs are synthetic boundary and behavior cases; they contain no credentials or real account identifiers.

`native-owned-instance-v1.jsonl` contains four expected constructor outputs captured from the existing World image against the pinned read-only catalog publication. The inputs use catalog references and synthetic entity IDs; no credentials, tokens, or player data are included.

These files are frozen compatibility fixtures. Tests compare the Rust contract and optional read-only native probe directly against the saved expected values; they do not import the retired Python service as an oracle.
