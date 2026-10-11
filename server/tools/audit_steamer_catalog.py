"""Read-only complete Steamer class closure from the published PostgreSQL authority."""
import audit_huppermage_catalog as reader

reader.BREED = 16
reader.EFFECT_PATHS += (
    "native-spell-casting.json",
    "native-class-triggered426-effect-closure.json",
)

if __name__ == "__main__":
    reader.main()
