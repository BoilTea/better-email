import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings

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
        captured = {}

        class FakeCompletions:
            def create(self, **kwargs):
                captured.update(kwargs)
                message = SimpleNamespace(
                    content="**Subject**: Approval needed\n\nHi Alex,\n\nPlease approve this.\n\nBest,\nSam"
                )
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=message)]
                )

        class FakeOpenAI:
            def __init__(self, **kwargs):
                captured["client"] = kwargs
                self.chat = SimpleNamespace(
                    completions=FakeCompletions()
                )

        with patch.object(app, "OpenAI", FakeOpenAI):
            result = app.draft_email(
                content="Ask Alex to approve the budget.",
                scenario="Request / ask",
                outcome="Approval by Friday",
                sender="Sam",
                receiver="Alex",
                model=app.DEFAULT_MODEL,
                api_key="test-key",
            )

        self.assertTrue(result.startswith("**Subject**:"))
        self.assertEqual(
            captured["client"]["base_url"],
            "https://api.siliconflow.cn/v1",
        )
        self.assertEqual(captured["extra_body"], {"enable_thinking": False})
        user_prompt = captured["messages"][1]["content"]
        self.assertIn("Scenario: Request / ask", user_prompt)
        self.assertIn("Desired outcome: Approval by Friday", user_prompt)


if __name__ == "__main__":
    unittest.main()
