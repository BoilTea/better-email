import os
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
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


class AsyncRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def setUp(self):
        test_case = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                content_length = int(self.headers.get("Content-Length", "0"))
                test_case.request_body = self.rfile.read(content_length)
                if test_case.response_delay:
                    time.sleep(test_case.response_delay)
                response = (
                    b'{"choices":[{"message":{"content":'
                    b'"**Subject**: Local test\\n\\nHi Alex,\\n\\nDone."}}]}'
                )
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(response)))
                    self.end_headers()
                    self.wfile.write(response)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, format, *args):
                pass

        self.request_body = b""
        self.response_delay = 0
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server_thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.server_thread.start()
        self.temp_directory = tempfile.TemporaryDirectory()
        settings = QSettings(
            os.path.join(self.temp_directory.name, "settings.ini"),
            QSettings.Format.IniFormat,
        )
        settings.setValue(
            app.CUSTOM_BASE_URL_SETTING,
            f"http://127.0.0.1:{self.server.server_port}/v1",
        )
        settings.setValue(app.CUSTOM_MODEL_SETTING, "local-test-model")

        self.window = app.EmailDrafterGUI()
        self.window.settings = settings
        self.window.refresh_model_dropdown()
        custom_index = self.window.model_dropdown.findData(app.CUSTOM_MODEL)
        self.window.model_dropdown.setCurrentIndex(custom_index)
        self.window.content_text.setPlainText("Tell Alex the task is done.")

    def tearDown(self):
        if self.window.active_reply is not None:
            self.window.cancel_generation()
            self.wait_until(lambda: self.window.active_reply is None)
        self.window.close()
        self.server.shutdown()
        self.server.server_close()
        self.temp_directory.cleanup()

    @staticmethod
    def wait_until(predicate, timeout_ms=2000):
        deadline = time.monotonic() + timeout_ms / 1000
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(10)
        return predicate()

    def test_request_completes_without_blocking_the_ui(self):
        self.window.generate_email()

        self.assertIsNotNone(self.window.active_reply)
        self.assertEqual(self.window.status_label.text(), "Writing…")
        self.assertTrue(self.wait_until(lambda: self.window.active_reply is None))
        self.assertEqual(self.window.status_label.text(), "Complete")
        self.assertIn("Local test", self.window.subject_text.toPlainText())
        self.assertIn(b'"model": "local-test-model"', self.request_body)

    def test_in_flight_request_can_be_cancelled(self):
        self.response_delay = 0.5
        self.window.generate_email()
        QTest.qWait(30)
        self.window.cancel_generation()

        self.assertTrue(self.wait_until(lambda: self.window.active_reply is None))
        self.assertEqual(self.window.status_label.text(), "Cancelled")
        self.assertEqual(self.window.submit_button.text(), "Generate email")


if __name__ == "__main__":
    unittest.main()
