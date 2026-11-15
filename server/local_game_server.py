"""World entry point; application domains own protocol and gameplay coordination."""


def main():
    from wakfu_server.application import bootstrap

    # The catalogue launcher supplies a prewarm receipt before importing World.
    prewarm = globals().get("_COMBAT_STARTUP_PREWARM")
    if prewarm is not None:
        bootstrap._COMBAT_STARTUP_PREWARM = prewarm
    bootstrap.main()


def __getattr__(name):
    """Keep existing diagnostic imports pointed at the one live application."""
    from wakfu_server.application import bootstrap

    return getattr(bootstrap, name)


if __name__ == "__main__":
    main()
