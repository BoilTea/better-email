import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

import email_drafter_gui as app


class PromptTests(unittest.TestCase):
    def test_token_estimate_handles_empty_ascii_and_cjk_text(self):
        self.assertEqual(app.estimate_prompt_tokens(""), 0)
        self.assertEqual(app.estimate_prompt_tokens("12345678"), 2)
        self.assertEqual(app.estimate_prompt_tokens("你好"), 2)

    def test_render_user_prompt_rejects_unknown_placeholder(self):
        with self.assertRaisesRegex(ValueError, "Unknown prompt placeholder"):
            app.render_user_prompt("Hello {unknown}", sender="Sam")

    def test_legacy_defaults_upgrade_without_overwriting_custom_prompts(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(
                os.path.join(directory, "settings.ini"),
                QSettings.Format.IniFormat,
            )
            settings.setValue(
                app.SYSTEM_PROMPT_SETTING,
                app.LEGACY_DEFAULT_SYSTEM_PROMPT,
            )
            upgraded = app.load_prompt_setting(
                settings,
                app.SYSTEM_PROMPT_SETTING,
                app.DEFAULT_SYSTEM_PROMPT,
                app.LEGACY_DEFAULT_SYSTEM_PROMPT,
            )
            self.assertEqual(upgraded, app.DEFAULT_SYSTEM_PROMPT)

            settings.setValue(app.SYSTEM_PROMPT_SETTING, "My custom prompt")
            custom = app.load_prompt_setting(
                settings,
                app.SYSTEM_PROMPT_SETTING,
                app.DEFAULT_SYSTEM_PROMPT,
                app.LEGACY_DEFAULT_SYSTEM_PROMPT,
            )
            self.assertEqual(custom, "My custom prompt")


class ModelRequestTests(unittest.TestCase):
    def test_qwen_request_uses_siliconflow_and_skill_fields(self):
        user_prompt = app.build_email_prompt(
            content="Ask Alex to approve the budget.",
            scenario="Request / ask",
            outcome="Approval by Friday",
            sender="Sam",
            receiver="Alex",
        )
        endpoint, payload = app.prepare_model_request(
            system_prompt=app.DEFAULT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=app.DEFAULT_MODEL,
            api_key="test-key",
        )

        self.assertEqual(
            endpoint,
            "https://api.siliconflow.cn/v1/chat/completions",
        )
        self.assertEqual(payload["enable_thinking"], False)
        sent_user_prompt = payload["messages"][1]["content"]
        self.assertEqual(payload["model"], app.DEFAULT_MODEL)
        self.assertIn("Scenario: Request / ask", sent_user_prompt)
        self.assertIn("Desired outcome: Approval by Friday", sent_user_prompt)

    def test_openai_compatible_response_is_parsed(self):
        response = (
            '{"choices":[{"message":{"content":'
            '"**Subject**: Approval needed\\n\\nHi Alex"}}]}'
        )
        result = app.parse_model_response(response, "test-model")
        self.assertTrue(result.startswith("**Subject**:"))


class CancellationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def test_cancel_aborts_active_reply(self):
        class FakeReply:
            aborted = False

            def abort(self):
                self.aborted = True

        window = app.EmailDrafterGUI()
        reply = FakeReply()
        window.active_reply = reply
        window.cancel_generation()

        self.assertTrue(reply.aborted)
        self.assertTrue(window.request_was_cancelled)
        self.assertEqual(window.status_label.text(), "Cancelling…")

        window.active_reply = None
        window.close()


if __name__ == "__main__":
    unittest.main()
