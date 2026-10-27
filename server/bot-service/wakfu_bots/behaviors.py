"""Composable external decision rules. No gameplay mutations happen here."""


class BuyerBehavior:
    name = "buyer"
    capability = "shop"
    world_capabilities = frozenset({"exchange"})

    def decide(self, event, settings, *, shop=None, llm=None):
        payload, event_type = event["payload"], event["type"]
        if event_type == "exchange.invited":
            return [("exchange.accept", {"exchange_id": payload["exchange_id"]})]
        if event_type != "exchange.updated" or payload.get("state") != "active":
            return []
        if shop is None:
            raise RuntimeError("Shop integration is unavailable")
        bot_character_id = payload["bot_character_id"]
        items = [
            item
            for item in payload.get("items", [])
            if item["character_id"] != bot_character_id
        ]
        members = payload.get("members", [])
        own = next(
            member for member in members if member["character_id"] == bot_character_id
        )
        args = {"exchange_id": payload["exchange_id"], "revision": payload["revision"]}
        if any(
            item["character_id"] == bot_character_id
            for item in payload.get("items", [])
        ) or any(
            member["offered_kamas"] != 0
            for member in members
            if member["character_id"] != bot_character_id
        ):
            return [("exchange.cancel", {"exchange_id": payload["exchange_id"]})]
        amount = shop.quote(items, settings.get("purchase_percent", 80)) if items else 0
        budget = payload.get("bot_kamas")
        if type(budget) is not int or budget < 0:
            raise ValueError("Exchange event lacks a valid bot budget")
        if amount is None or amount > budget:
            return [("exchange.cancel", {"exchange_id": payload["exchange_id"]})]
        if own["offered_kamas"] != amount:
            return [("exchange.offer_kamas", dict(args, amount=amount))]
        if (
            items
            and amount > 0
            and own.get("confirmed_revision") != payload["revision"]
        ):
            return [("exchange.ready", args)]
        return []


class LlmBehavior:
    name = "llm"
    capability = "llm"
    world_capabilities = frozenset({"chat"})

    def decide(self, event, settings, *, shop=None, llm=None):
        if (
            event["type"] != "chat.message"
            or event["payload"].get("addressed") is not True
        ):
            return []
        if llm is None:
            raise RuntimeError("Optional LLM integration is unavailable")
        text = event["payload"].get("text")
        if not isinstance(text, str) or not text.strip() or len(text.encode()) > 2048:
            raise ValueError("Invalid conversation event")
        reply = llm.reply(event["bot_id"], settings.get("personality", ""), text)
        if event["payload"].get("channel") == "private":
            recipient = event["payload"].get("sender_name")
            if not isinstance(recipient, str) or not recipient:
                raise ValueError("Private conversation lacks a sender")
            return [("whisper", {"recipient": recipient, "text": reply})]
        return [("say", {"text": reply})]


class AnnouncerBehavior:
    name = "announcer"
    capability = None
    world_capabilities = frozenset({"chat"})

    def decide(self, event, settings, *, shop=None, llm=None):
        if event["type"] == "timer.announcement":
            return [("say", {"text": settings["text"]})]
        return []


class BehaviorRegistry:
    def __init__(self, behaviors=None):
        self.behaviors = {}
        for behavior in (
            behaviors
            if behaviors is not None
            else (BuyerBehavior(), LlmBehavior(), AnnouncerBehavior())
        ):
            self.register(behavior)

    def register(self, behavior):
        if behavior.name in self.behaviors:
            raise ValueError("Behavior already registered")
        self.behaviors[behavior.name] = behavior

    def world_capabilities(self, profile):
        capabilities = set()
        for name in profile["behaviors"]:
            capabilities.update(self.behaviors[name].world_capabilities)
        return sorted(capabilities)

    def decide(self, profile, event, *, shop=None, llm=None):
        actions = []
        for name, settings in profile["behaviors"].items():
            behavior = self.behaviors[name]
            if (
                behavior.capability is not None
                and behavior.capability not in profile["capabilities"]
            ):
                raise PermissionError("Bot lacks the behavior integration capability")
            actions.extend(
                behavior.decide(
                    event,
                    settings,
                    shop=shop if "shop" in profile["capabilities"] else None,
                    llm=llm if "llm" in profile["capabilities"] else None,
                )
            )
        return actions
