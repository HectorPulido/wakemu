"""Exercise the real save dispatcher without starting network services."""
import sys
from types import SimpleNamespace
import pathlib
import textwrap
import unittest
from unittest.mock import Mock, patch


class BuildSaveDispatchTest(unittest.TestCase):
    def dispatch(
        self,
        decoded=None,
        decode_error=None,
        changed_inventory=False,
        hero=False,
        save_error=None,
        real_response=False,
    ):
        source = pathlib.Path(__file__).resolve().parents[1] / "local_game_server.py"
        branch = source.read_text().split("elif opcode == 12772 and loaded:", 1)[1]
        branch = branch.split("elif opcode == 13578 and loaded:", 1)[0]
        branch = textwrap.dedent(branch).replace("continue", "return")
        current = {"id": 37, "active_build_index": 0, "inventory_items": []}
        if real_response:
            from wakfu_server import wire

            sheet = b"".join(
                wire.proto_field(tag, value)
                for tag, value in [(8, 0), (18, b"Saved"), (24, 20), (56, 0), (64, 1)]
            )
            current.update(
                level=20,
                effective_level=20,
                breed=8,
                map_id=1134,
                instance_id=0,
                direction=0,
                x=0,
                y=0,
                z=0,
                name="Saved",
                hp=500,
                max_hp=500,
                builds={
                    0: {
                        "sheet": sheet.hex(),
                        "equipment": "",
                        "deck": "",
                        "aptitudes": "",
                    }
                },
            )
        saved = dict(current, inventory_items=[{"uid": 1}] if changed_inventory else [])
        if hero:
            saved = dict(saved, id=40)
        builds = Mock()
        builds.decode.return_value = decoded or (40 if hero else 37, 0, {})
        builds.decode.side_effect = decode_error
        builds.valid_index.return_value = True
        builds.capacity_message.return_value = (22318, b"")
        builds.rejection_messages.return_value = [(12284, b"rejected")]
        builds.response_messages.return_value = [(12284, b"saved")]
        if real_response:
            from wakfu_server import builds as real_builds

            builds.response_messages.side_effect = real_builds.response_messages
        store = Mock()
        store.save_build.return_value = saved
        store.character.return_value = dict(current, id=40) if hero else current
        store.save_build.side_effect = save_error
        context = dict(
            character=current,
            builds=builds,
            STORE=store,
            body=b"",
            account_id=1,
            generation="lease",
            COMBAT_TEST_WP=6,
            connection=object(),
            service="world",
            fight=None,
            combat_session=None,
            OWNED_HERO_TEMPLATE=b"",
            send=Mock(),
            record=Mock(),
            active_private_session=lambda: None,
            publish_mount_equipment=Mock(),
        )
        exec(
            "def run():\n    global character\n" + textwrap.indent(branch, "    "),
            context,
        )
        from wakfu_server import characters

        hero_wire = SimpleNamespace(
            refresh=lambda template, actor: (13046, b"hero"),
            statistics=lambda actor: (15548, b"stats"),
        )
        with patch.object(characters, "hero_wire", hero_wire, create=True), patch.dict(
            sys.modules,
            {
                "wakfu_server.inventory_move": SimpleNamespace(
                    synchronization=lambda actor: (13713, b"bags")
                ),
                "wakfu_server.inventory_items": SimpleNamespace(
                    equipment_inventory=lambda actor: (13078, b"gear")
                ),
            },
        ), patch("wakfu_server.spells.default_deck", return_value=b""), patch(
            "wakfu_server.combat_lifecycle.outside_progression",
            return_value=(13046, b"authoritative-actor"),
        ):
            context["run"]()
        return context

    def test_invalid_target_rejected_without_save_or_disconnect(self):
        context = self.dispatch(decoded=(0, 0, {}))
        context["STORE"].save_build.assert_not_called()
        self.assertEqual(context["send"].call_args_list[-1].args[-1], b"rejected")
        self.assertEqual(context["character"]["id"], 37)

    def test_malformed_packet_rejected_without_save_or_disconnect(self):
        context = self.dispatch(decode_error=ValueError("Truncated or invalid length"))
        context["STORE"].save_build.assert_not_called()
        self.assertEqual(context["send"].call_args_list[-1].args[-1], b"rejected")

    def test_successful_split_publishes_updated_inventory_before_ack(self):
        context = self.dispatch(changed_inventory=True)
        context["STORE"].save_build.assert_called_once_with(1, "lease", 37, 0, {})
        self.assertEqual(
            [call.args[2] for call in context["send"].call_args_list],
            [13713, 13078, 22318, 12284],
        )

    def test_success_without_split_preserves_response_sequence(self):
        context = self.dispatch()
        self.assertEqual(
            [call.args[2] for call in context["send"].call_args_list], [22318, 12284]
        )

    def test_successful_save_uses_real_ack_aptitudes_and_actor_refresh_without_registry_replacement(
        self,
    ):
        context = self.dispatch(real_response=True)
        context["STORE"].save_build.assert_called_once_with(1, "lease", 37, 0, {})
        self.assertEqual(
            [call.args[2] for call in context["send"].call_args_list],
            [22318, 12284, 12103, 13046],
        )

    def test_owned_hero_save_does_not_replace_selected_main(self):
        context = self.dispatch(hero=True)
        context["STORE"].save_build.assert_called_once_with(1, "lease", 40, 0, {})
        self.assertEqual(context["character"]["id"], 37)
        self.assertEqual(
            [call.args[2] for call in context["send"].call_args_list],
            [22318, 12284, 13046, 15548],
        )

    def test_inactive_or_foreign_target_save_rejection_keeps_main(self):
        context = self.dispatch(
            hero=True,
            save_error=ValueError("Build character is not an active owned hero"),
        )
        self.assertEqual(context["character"]["id"], 37)
        self.assertEqual(
            [call.args[2] for call in context["send"].call_args_list], [22318, 12284]
        )


if __name__ == "__main__":
    unittest.main()
