"""Run the separate Wakemu bot behavior service."""
import logging
import os
import threading
from pathlib import Path

from wakfu_bots.clients import JsonClient, LlmClient, ShopClient, WorldClient
from wakfu_bots.config import Profiles
from wakfu_bots.http import make_server
from wakfu_bots.runtime import Worker


def read_token(variable, *, required=True):
    path = os.environ.get(variable)
    if not path:
        if required:
            raise ValueError(f"{variable} is required")
        return ""
    token = Path(path).read_text().strip()
    if len(token) < 24:
        raise ValueError(f"{variable} contains an invalid credential")
    return token


def main():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    profiles = Profiles(
        os.environ.get("WAKFU_BOTS_PROFILES_FILE", "/data/profiles.json")
    )
    world = WorldClient(
        os.environ.get("WAKFU_WORLD_URL", "http://world:18081"),
        read_token("WAKFU_BOTS_TOKEN_FILE"),
    )
    shop_url = os.environ.get("WAKFU_SHOP_URL", "http://shop:18083")
    shop = ShopClient(JsonClient(shop_url)) if shop_url else None
    llm_url = os.environ.get("WAKFU_BOTS_LLM_URL", "")
    llm = (
        LlmClient(
            JsonClient(
                llm_url,
                read_token("WAKFU_BOTS_LLM_TOKEN_FILE", required=False),
                timeout=10,
            )
        )
        if llm_url
        else None
    )
    worker = Worker(
        profiles,
        world,
        shop=shop,
        llm=llm,
        state_path=os.environ.get("WAKFU_BOTS_STATE_FILE", "/data/worker-state.json"),
    )
    server = make_server(
        worker,
        read_token("WAKFU_BOTS_ADMIN_TOKEN_FILE"),
        os.environ.get("WAKFU_BOTS_HOST", "0.0.0.0"),
        int(os.environ.get("WAKFU_BOTS_PORT", "8096")),
    )
    thread = threading.Thread(
        target=worker.run, name="wakemu-bot-behaviors", daemon=True
    )
    thread.start()
    try:
        server.serve_forever()
    finally:
        worker.stop.set()
        server.server_close()
        thread.join(timeout=15)


if __name__ == "__main__":
    main()
