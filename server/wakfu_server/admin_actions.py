"""Panel actions delegated to the authoritative character session thread."""
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class AdminActions:
    def _world(self, path, data=None):
        token_file = os.environ.get("WAKFU_ADMIN_WORLD_TOKEN_FILE")
        if not token_file:
            raise ValueError("World administration credential is not configured")
        token = Path(token_file).read_text().strip()
        address = os.environ.get("WAKFU_WORLD_URL", "http://world:18081").rstrip("/")
        request = Request(
            address + path,
            data=json.dumps(data).encode() if data is not None else None,
            headers={
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=5) as response:
                return json.loads(response.read(1048576))
        except HTTPError as error:
            # World errors may be localized. Keep the panel language consistent.
            error.read(8192)
            message = {
                401: "World administration credential expired or was revoked",
                403: "World administration permission was denied",
                404: "World action endpoint or receipt was not found",
                400: "World rejected the action; refresh character presence and retry",
            }
            raise ValueError(
                message.get(error.code, "World is unavailable; no action was confirmed")
            ) from None
        except (URLError, TimeoutError):
            raise ValueError("World is unavailable; no action was confirmed") from None

    def characters(self, q="", limit=50, offset=0):
        with self.store.connection() as db:
            result = self._list(
                db,
                "SELECT c.id,c.account_id,a.username,c.name,c.level,c.map_id,c.instance_id,c.x,c.y,c.z,EXISTS(SELECT 1 FROM sessions s WHERE s.character_id=c.id AND s.expires_at>now()) online FROM characters c JOIN accounts a ON a.id=c.account_id WHERE c.deleted_at IS NULL AND (c.name ILIKE %s OR a.username ILIKE %s OR c.id::text=%s) ORDER BY c.id",
                ("%" + str(q)[:100] + "%", "%" + str(q)[:100] + "%", str(q)[:100]),
                limit,
                offset,
            )
        from wakfu_server.admin_positions import present

        result["items"] = present(self.store, result["items"])
        return result

    def character(self, character_id):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT c.id,c.account_id,a.username,c.name,c.breed,c.level,c.hp,c.max_hp,c.map_id,c.instance_id,c.x,c.y,c.z,EXISTS(SELECT 1 FROM sessions s WHERE s.character_id=c.id AND s.expires_at>now()) online FROM characters c JOIN accounts a ON a.id=c.account_id WHERE c.id=%s AND c.deleted_at IS NULL",
                (character_id,),
            ).fetchone()
            if row is None:
                raise LookupError("Character not found")
            result = dict(row)
            result["inventory"] = [
                dict(r)
                for r in db.execute(
                    "SELECT uid,reference,quantity,container,slot FROM inventory_items WHERE character_id=%s ORDER BY container,slot",
                    (character_id,),
                )
            ]
            result["containers"] = [
                dict(r)
                for r in db.execute(
                    "SELECT uid,capacity FROM inventory_containers WHERE character_id=%s ORDER BY uid",
                    (character_id,),
                )
            ]
        from wakfu_server.admin_positions import present

        return present(self.store, [result])[0]

    def _submit_action(self, character_id, command, data, operator, action):
        self.character(character_id)
        request_id = data.get("request_id")
        if not isinstance(request_id, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,100}", request_id
        ):
            raise ValueError(
                "A unique request_id is required (letters, numbers, underscores or hyphens)"
            )
        # World presence is authoritative: stale database leases cannot grant items.
        sessions = self._world("/test/admin-sessions")
        if not any(row["character_id"] == character_id for row in sessions):
            raise ValueError(
                "Character is offline; connect it before performing this action"
            )
        receipt = self._world(
            "/test/admin-command",
            dict(character_id=character_id, command=command, request_id=request_id),
        )
        with self.store.connection() as db:
            self._audit(
                db,
                operator,
                action,
                character_id,
                None,
                dict(
                    request_id=request_id,
                    receipt_handle=receipt["handle"],
                    status=receipt["status"],
                    parameters={k: v for k, v in data.items() if k != "request_id"},
                ),
            )
        return self._action_receipt(receipt)

    def grant_item(self, character_id, data, operator):
        if not isinstance(data, dict) or set(data) - {
            "item_ref",
            "quantity",
            "request_id",
        }:
            raise ValueError("Unsupported item delivery field")
        reference = self.integer(data.get("item_ref"), 1, 2147483647, "item reference")
        quantity = self.integer(data.get("quantity"), 1, 32767, "quantity")
        with self.store.connection() as db:
            rule = db.execute(
                "SELECT payload FROM native_catalog_records WHERE revision=(SELECT revision FROM native_catalog_active WHERE id=1) AND path='item-stack-rules.json' AND collection='items' AND record_key=%s",
                (str(reference),),
            ).fetchone()
        if rule is None or quantity > min(int(rule["payload"]["maximum"]), 32767):
            raise ValueError(
                "Item or quantity is unsupported by the native stack catalog"
            )
        return self._submit_action(
            character_id,
            f"!item {reference} {quantity}",
            data,
            operator,
            "character.item_delivery",
        )

    def teleport_character(self, character_id, data, operator):
        if not isinstance(data, dict) or set(data) - {
            "map_id",
            "x",
            "y",
            "z",
            "request_id",
        }:
            raise ValueError("Unsupported teleport field")
        map_id = self.integer(data.get("map_id"), 0, 2147483647, "map")
        coordinates = [
            self.integer(data.get(axis), -32768, 32767, axis)
            for axis in ("x", "y", "z")
        ]
        self.map(map_id)
        # The world rechecks native walkability and combat/Haven Bag state.
        command = "!tp " + " ".join(str(value) for value in (map_id, *coordinates))
        return self._submit_action(
            character_id, command, data, operator, "character.teleport"
        )

    @staticmethod
    def _action_receipt(receipt):
        result = dict(receipt)
        if result.get("status") == "completed":
            details = result.get("result")
            if isinstance(details, dict):
                details = dict(details)
                details["message"] = "Action completed by the world server"
                result["result"] = details
        if "error" in result:
            translations = {
                "El inventario está lleno": "Inventory is full; free a slot and retry",
                "Termina el combate antes de modificar el mundo o el inventario.": "Finish the fight before changing inventory or location",
                "Sal del combate o del merkasaco antes de usar este comando.": "Leave combat or the Haven Bag before teleporting",
                "La casilla de destino no es transitable en la geometría nativa": "Destination is not walkable in the native map geometry",
                "La sesión terminó antes de ejecutar el comando": "Character disconnected before the action executed",
            }
            result["error"] = translations.get(
                result["error"],
                "World rejected the action; refresh the character state and verify the item or destination",
            )
        return result

    def action(self, handle):
        if not isinstance(handle, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,100}", handle
        ):
            raise ValueError("Invalid action handle")
        return self._action_receipt(self._world("/test/command/" + handle))
