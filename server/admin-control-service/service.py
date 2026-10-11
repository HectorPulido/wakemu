"""Start the private Docker control broker; never expose its socket to the panel."""
import os
from pathlib import Path
from wakfu_server.admin_control import DockerControl, OperationManager, make_server

control = DockerControl(
    os.environ["HOST_PROJECT_ROOT"],
    os.environ.get("WAKFU_COMPOSE_PROJECT", "wakfu-local"),
    "/data",
)
manager = OperationManager(control, "/data")
token = Path(os.environ["WAKFU_ADMIN_CONTROL_TOKEN_FILE"]).read_text().strip()
server = make_server(
    manager, token, port=int(os.environ.get("WAKFU_ADMIN_CONTROL_PORT", "18085"))
)
try:
    server.serve_forever()
finally:
    server.server_close()
