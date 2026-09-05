"""
Unit tests for Telegram Human-in-the-Loop review card and callback buttons.
Location: tests/gateway/test_telegram_human_review_buttons.py
"""
import asyncio
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

_repo = str(Path(__file__).resolve().parents[2])
if _repo not in sys.path:
    sys.path.insert(0, _repo)

from gateway.config import Platform, PlatformConfig
from plugins.platforms.telegram.adapter import TelegramAdapter


def _make_adapter():
    config = PlatformConfig(enabled=True, token="test-token", extra={})
    adapter = TelegramAdapter(config)
    adapter._bot = AsyncMock()
    adapter._app = MagicMock()
    return adapter


class TestTelegramHumanReviewButtons(unittest.IsolatedAsyncioTestCase):
    """Verifies Telegram interactive HITL cards, buttons, and callback handlers."""

    async def test_send_human_review_buttons_and_limits(self):
        adapter = _make_adapter()
        mock_msg = MagicMock()
        mock_msg.message_id = 99
        adapter._bot.send_message = AsyncMock(return_value=mock_msg)

        item = {
            "item_id": "rev_a1b2c3d4",
            "task_id": "task_database_migration",
            "category": "security_risk",
            "title": "Approve elevated migration permissions",
            "description": "Migration requires altering table schema.",
            "proposed_options": [
                {"id": 1, "text": "Set pool size to 50"},
                {"id": 2, "text": "Set pool size to 100"},
            ],
            "urgency": "blocking",
        }

        result = await adapter.send_human_review(chat_id="12345", item=item)
        self.assertTrue(result.success)
        self.assertEqual(result.message_id, "99")

        adapter._bot.send_message.assert_called_once()
        kwargs = adapter._bot.send_message.call_args[1]

        # Verify HTML text and content
        self.assertIn("SUPERGRAPH HITL", kwargs["text"])
        self.assertIn("task_database_migration", kwargs["text"])
        self.assertIn("BLOCKING", kwargs["text"])

        # Verify InlineKeyboardMarkup
        keyboard = kwargs["reply_markup"]
        self.assertIsNotNone(keyboard)

        # Flatten buttons
        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        self.assertEqual(len(all_buttons), 3)  # Option 1, Option 2, Abort

        # Verify 64-byte limit on all callback_data tokens
        for btn in all_buttons:
            cb_data = btn.callback_data
            self.assertTrue(cb_data.startswith("hr:"))
            self.assertLess(len(cb_data.encode("utf-8")), 64, f"Callback data {cb_data} exceeds 64 bytes!")

        # Verify callback content
        self.assertEqual(all_buttons[0].callback_data, "hr:1:a1b2c3d4")
        self.assertEqual(all_buttons[1].callback_data, "hr:2:a1b2c3d4")
        self.assertEqual(all_buttons[2].callback_data, "hr:abort:a1b2c3d4")

    async def test_hr_callback_query_resolution_approve(self):
        adapter = _make_adapter()
        adapter._human_review_state = {"a1b2c3d4": "rev_a1b2c3d4"}
        adapter._is_callback_user_authorized = MagicMock(return_value=True)

        query = AsyncMock()
        query.data = "hr:1:a1b2c3d4"
        query.from_user = SimpleNamespace(id=12345, first_name="Ales")
        query.message = AsyncMock()
        query.message.text = "Review card text"
        query.message.text_html = "Review card text"

        # Mock urllib.request.urlopen to simulate Bridge resolve success
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            update = SimpleNamespace(callback_query=query)
            await adapter._handle_callback_query(update, MagicMock())

            # Verify resolve endpoint was called
            self.assertEqual(mock_urlopen.call_count, 1)
            req_arg = mock_urlopen.call_args[0][0]
            self.assertIn("/v1/bridge/human_queue/resolve", req_arg.full_url)

            # Verify query answer and message edit
            query.answer.assert_called_once()
            self.assertIn("Approved", query.answer.call_args[1]["text"])
            query.message.edit_text.assert_called_once()

    async def test_hr_callback_query_resolution_abort(self):
        adapter = _make_adapter()
        adapter._human_review_state = {"b2c3d4e5": "rev_b2c3d4e5"}
        adapter._is_callback_user_authorized = MagicMock(return_value=True)

        query = AsyncMock()
        query.data = "hr:abort:b2c3d4e5"
        query.from_user = SimpleNamespace(id=12345, first_name="Ales")
        query.message = AsyncMock()
        query.message.text = "Review card text"
        query.message.text_html = "Review card text"

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            update = SimpleNamespace(callback_query=query)
            await adapter._handle_callback_query(update, MagicMock())

            self.assertEqual(mock_urlopen.call_count, 1)
            req_arg = mock_urlopen.call_args[0][0]
            req_payload = json.loads(req_arg.data.decode("utf-8"))
            self.assertEqual(req_payload["action"], "reject")
            self.assertEqual(req_payload["item_id"], "rev_b2c3d4e5")

            query.answer.assert_called_once()
            self.assertIn("Aborted", query.answer.call_args[1]["text"])
            query.message.edit_text.assert_called_once()


if __name__ == "__main__":
    unittest.main()
