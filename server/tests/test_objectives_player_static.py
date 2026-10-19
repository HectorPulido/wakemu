"""Static embed lifecycle checks without a browser or external DOM package."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest

from wakfu_server.objectives.player_views import achievement_type

STATIC = Path(__file__).resolve().parents[1] / "objectives-service" / "static"
ADMIN_JS = Path(__file__).resolve().parents[1] / "admin-service" / "static" / "admin.js"


class ObjectivesPlayerStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (STATIC / "index.html").read_text()
        cls.js = (STATIC / "adventures.js").read_text()
        cls.admin_js = ADMIN_JS.read_text()

    def test_page_uses_referrer_protection_and_keyboard_tab_semantics(self):
        self.assertRegex(self.html, r'<meta\s+name="referrer"\s+content="no-referrer"')
        self.assertIn('role="tablist"', self.html)
        self.assertIn('aria-selected="true"', self.html)
        self.assertIn('aria-controls="panel-board"', self.html)
        self.assertIn('data-tab="first_steps"', self.html)
        self.assertIn("ArrowRight", self.js)
        self.assertIn("ArrowLeft", self.js)

    def test_launch_token_is_removed_before_exchange_and_never_falls_back(self):
        start = self.js[self.js.index("async function start()") :]
        clear_fragment = start.index("history.replaceState")
        clear_saved = start.index("storage.remove('wakemu.adventures.session')")
        exchange = start.index("api('/session'")
        clear_credential = start.index("credential = null")
        self.assertLess(clear_fragment, exchange)
        self.assertLess(clear_saved, exchange)
        self.assertLess(clear_credential, exchange)
        self.assertIn("if (launchToken) {", start)
        self.assertIn("if (!credential) { stop(", start)
        self.assertNotIn("localStorage", self.js)
        self.assertNotIn("WAKFU_OBJECTIVES_TOKEN", self.js)

    def test_untrusted_content_uses_text_nodes_and_embed_has_no_parent_channel(self):
        self.assertNotRegex(self.js, r"\.innerHTML\s*=")
        self.assertIn("element.textContent = String(text)", self.js)
        self.assertIn("textContent =", self.js)
        self.assertNotIn("postMessage", self.js)
        self.assertNotIn("window.parent", self.js)
        self.assertNotIn("parentOrigin", self.js)
        self.assertNotIn("allowedParents", self.js)
        self.assertNotIn('id="close"', self.html)
        self.assertIn("credentials: 'same-origin'", self.js)
        self.assertIn("referrerPolicy: 'no-referrer'", self.js)

    def test_action_uses_request_id_for_replay_and_server_receipt_id_for_polling(self):
        self.assertIn("crypto.randomUUID()", self.js)
        self.assertIn(
            "JSON.stringify({ action_key: action.key, request_id: requestId })", self.js
        )
        self.assertIn("api(`/actions/${encodeURIComponent(current.id)}`)", self.js)
        self.assertIn("status === 'unknown'", self.js)
        self.assertIn("Replay only the exact same idempotency key", self.js)
        # Browser intent contains no target coordinates; target resolution is
        # an authoritative server action lookup.
        self.assertNotRegex(self.js, r"JSON\.stringify\(\{[^}]*target\s*:")

    def test_native_reward_preview_keeps_kamas_xp_emote_title_and_item_distinct(self):
        self.assertIn("reward.kind === 'kamas'", self.js)
        self.assertIn("reward.aeV === 6", self.js)
        self.assertIn("XP`", self.js)
        self.assertIn("reward.aeV === 3", self.js)
        self.assertIn("Emote #", self.js)
        self.assertIn("reward.aeV === 2", self.js)
        self.assertIn("reward.aeV === 5", self.js)

    def test_admin_player_link_button_uses_csrf_and_validates_reusable_url(self):
        self.assertIn(
            "if (options.method && options.method !== 'GET' && session?.csrf_token)",
            self.admin_js,
        )
        self.assertIn("api('/objectives/player-launch'", self.admin_js)
        self.assertIn("character_id:Number(characterID)", self.admin_js)
        self.assertIn("result.valid_days||30", self.admin_js)
        self.assertIn("['http:','https:'].includes(url.protocol)", self.admin_js)
        self.assertIn("['/player','/player/'].includes(url.pathname)", self.admin_js)
        self.assertIn("popup.opener=null", self.admin_js)
        self.assertIn(
            "reusable link works for 30 days, including while the account is offline",
            self.admin_js,
        )

    def test_hourly_pvp_panel_uses_live_event_actions_and_true_frame_edges(self):
        render = self.js[
            self.js.index("function renderPvp(data)") : self.js.index(
                "function displayWeek(value)"
            )
        ]
        self.assertIn("data.pvp?.current", render)
        self.assertIn("match.dataset.status = event.status", render)
        self.assertIn("role', 'timer'", render)
        self.assertIn("actionList(event.actions)", render)
        self.assertIn("data.pvp?.history", render)
        self.assertIn(
            "entry.winner?.account_id === entry.participant_one?.account_id", render
        )
        self.assertNotIn("data.sections?.pvp", render)
        self.assertNotIn("data.pvp_history", render)

        css = (STATIC / "adventures.css").read_text()
        self.assertRegex(css, r"body\{margin:0;padding:0;")
        self.assertRegex(
            css, r"\.adventures\{width:100%;margin:0;border:0;border-radius:0;"
        )
        self.assertIn("min-height:100dvh", css)

    def test_board_uses_public_hunt_and_server_assigned_periodic_cards(self):
        render = self.js[
            self.js.index("function renderBoard(data)") : self.js.index(
                "function achievementGroup(card)"
            )
        ]
        self.assertIn("const hunt = data.hunt", render)
        self.assertIn("hunt.monster_name", render)
        self.assertIn("hunt.map_name", render)
        self.assertIn("hunt.status", render)
        self.assertIn("hunt.clue", render)
        self.assertIn("hunt.rewards", render)
        self.assertIn("sections.daily || []", render)
        self.assertIn("sections.weekly || []", render)
        self.assertIn("sections.almanax || []", render)
        self.assertIn("data.ranking || []", render)
        self.assertIn("entry.points", render)
        self.assertNotIn("data.sections?.missions", render)
        self.assertNotIn("weekly.enter", render)

    def test_achievement_groups_follow_fact_type_not_key_or_map_name(self):
        group = self.js[
            self.js.index("function achievementGroup(card)") : self.js.index(
                "function renderFirstSteps(data)"
            )
        ]
        self.assertIn("card.achievement_type", group)
        self.assertIn("area.dataset.zoneKey = group.key", group)
        self.assertNotIn("card.zone", group)
        self.assertIn("characters: 'Characters'", group)
        self.assertIn("professions: 'Professions'", group)
        self.assertEqual(
            achievement_type(
                {
                    "key": "content-v1.map.527",
                    "objectives": [
                        {"event": "dungeon_completed"},
                    ],
                }
            ),
            "dungeons",
        )
        self.assertEqual(
            achievement_type(
                {
                    "key": "arbitrary.527.map",
                    "objectives": [
                        {"event": "original_monster_killed"},
                    ],
                }
            ),
            "monsters",
        )
        self.assertEqual(
            achievement_type(
                {
                    "key": "progression-v1.characters.level.100",
                    "objectives": [
                        {"event": "account_character_level_progressed"},
                    ],
                }
            ),
            "characters",
        )
        self.assertEqual(
            achievement_type(
                {
                    "key": "progression-v1.professions.level.100.count.1",
                    "objectives": [
                        {"event": "account_profession_level_progressed"},
                    ],
                }
            ),
            "professions",
        )
        self.assertEqual(
            achievement_type(
                {
                    "key": "anything",
                    "objectives": [
                        {"event": "map_entered"},
                        {"event": "resource_harvested"},
                    ],
                }
            ),
            "other",
        )
        self.assertEqual(
            achievement_type(
                {
                    "key": "unknown",
                    "objectives": [{"event": "made_up_event"}],
                }
            ),
            "other",
        )

    @unittest.skipUnless(
        shutil.which("node"), "Node.js is needed for JavaScript syntax validation"
    )
    def test_javascript_parses(self):
        result = subprocess.run(
            [shutil.which("node"), "--check", str(STATIC / "adventures.js")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
