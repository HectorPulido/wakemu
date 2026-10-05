#!/usr/bin/env python3
"""Critical Cinetosis and original Asalto swap through the common cast engine."""
from audit_displacement_spell_reactions import run

if __name__ == "__main__":
    run(
        scenarios=(
            (5041, "normal", 5030, True),
            (5041, "normal", 5040, False),
            (5041, "push_zone", 5030, False),
        ),
        output_name="docs/reports/combat-inventory/cinetosis-movement-variants-runtime-audit.json",
    )
