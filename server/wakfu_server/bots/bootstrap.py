"""Optional bot transport startup; World never loads behavior providers."""
import threading

from .bridge import BotWorldBridge
from .runtime import BotsRuntime


def configure(
    *, store, world, exchanges, positions, token, say, whisper, stopping, record
):
    runtime = BotsRuntime(
        store,
        world,
        exchanges,
        positions,
        say=say,
        whisper=whisper,
        emit=lambda *args: None,
    )
    bridge = BotWorldBridge(runtime, token)
    runtime.emit = bridge.emit
    exchanges.bot_delivery = runtime.handle_exchange

    def maintain():
        while not stopping.wait(5):
            try:
                bridge.tick()
            except Exception as error:
                record(event="bot_runtime_tick_failed", reason=type(error).__name__)
        try:
            runtime.deactivate_all()
        except Exception as error:
            record(event="bot_runtime_shutdown_failed", reason=type(error).__name__)

    threading.Thread(target=maintain, name="wakfu-bot-authority", daemon=True).start()
    return bridge
