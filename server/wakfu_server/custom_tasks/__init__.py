"""Server-owned custom tasks, separate from installed native journal identities.

Only authoritative gameplay adapters may submit events. This package validates
facts and persistence but does not prove kills, seed consumption or session
leases. Callers must authorize those before entering this domain transaction.
"""
