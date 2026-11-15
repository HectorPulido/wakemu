"""Account transport discovery policy shared by world entry and travel."""


class TravelPolicy:
    def __init__(self, runtime):
        self.runtime = runtime

    def known_transports(self, account_id):
        return self.runtime.transport_discovery.local_policy(
            self.runtime.TRANSPORT_DISCOVERIES.known(account_id),
            all_zaaps=self.runtime.ALL_ZAAPS,
            all_dragos=self.runtime.ALL_DRAGOS,
        )
