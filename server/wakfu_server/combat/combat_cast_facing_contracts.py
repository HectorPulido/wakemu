"""Source-attested literal no-turn parameters outside the original extractor.

Read-only installed Lua witnesses, scripts.jar SHA256:
fd55b37304f77d2f8db202fd4147658cb2f7af960ac36a4876b1588093bb5c7b.
These attest only the named parameters, not the entire script execution.
Matching uses the catalog's actual script ID, never an inferred spell family.
"""
from types import MappingProxyType

SCRIPT_CONTRACTS = MappingProxyType(
    {
        -1797056500: MappingProxyType(
            {
                "script_content_sha256": "1fb338a6717e446aff3e1488db8a4ea22c6b0a9f49af84974b450098701ba38a",
                "parameter_table": "params",
                "invoked_template": 1023,
                "turnCasterTowardTargetCell": False,
            }
        ),
        -1142083330: MappingProxyType(
            {
                "script_content_sha256": "85b0a232ac0f95b4946d3e532e9e128be92b5e7da35f9fb20e4a7988fbd7934d",
                "parameter_table": "params_start",
                "invoked_template": 1040,
                "turnCasterTowardTargetCell": False,
            }
        ),
    }
)
